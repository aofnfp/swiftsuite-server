import os
import time
import csv
import pandas as pd
from ftplib import FTP
from threading import Thread
from django.http import JsonResponse
from .models import Lipsey, Ssi, Zanders, Generalproducttable, Fragrancex, Cwr, Rsr
from .apiSupplier import getFragranceXData, getRSR

def compute_price(productCost, fixedVendorMarkup, percentageVendorMarkup, shipping_cost):
    
    productCost = float(productCost)
    totalProductCost = productCost + float(fixedVendorMarkup) + ((float(percentageVendorMarkup)/100) * productCost) + float(shipping_cost)
    totalProductCost = round(totalProductCost, 2)
    return str(totalProductCost)

def pull_vendor_update(supplier_name, userid, ftp_host='', ftp_user='', ftp_password='', apiAccessId='', apiAccessKey='', username='', password='', pos='I'):
    try:
        update_dir = os.path.join("update_dir", supplier_name)
        os.makedirs(update_dir, exist_ok=True)

        file_name = ''
        
        if supplier_name == 'FragranceX':
            data = getFragranceXData(apiAccessId, apiAccessKey)
            file_name = "fragrancex.csv"
            file_path = os.path.join(update_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                if 'RetailPriceUSD' not in data[3].keys():
                    data[3]['RetailPriceUSD'] = 0
                writer = csv.DictWriter(file, fieldnames=data[3].keys())
                writer.writeheader()
                writer.writerows(data)

            # print(f"Data successfully written to {file_path}")
            process_fragrancex(file_path, userid)

        elif supplier_name == 'RSR':
            
            data = getRSR(username, password, pos)
            file_name = "rsr.csv"
            file_path = os.path.join(update_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

            # print(f"Data successfully written to {file_path}")
            process_rsr(file_path, userid)
            

        else:
            port = 21
            if supplier_name == 'Lipsey':
                file_name='pricingquantity.csv'
                ftp_path = '/'


            elif supplier_name == 'SSI':
                file_name='RR_Pricing_Availability.csv'
                ftp_path = '/Pricing-Availability'

            elif supplier_name == 'Zanders':
                file_name='liveinv.csv'
                ftp_path='/Inventory'
                file2_name = "zandersinv.csv"

            elif supplier_name == 'CWR':
                file_name='inventory.csv'
                ftp_path='/out'
            
            # FTP connection
            ftp = FTP()
            ftp.connect(ftp_host, port)
            ftp.login(user=ftp_user, passwd=ftp_password)
            ftp.set_pasv(True)
            ftp.cwd(ftp_path)
            
            # Download file from FTP
            with open(os.path.join(update_dir, file_name), "wb") as local_file:
                ftp.retrbinary(f"RETR {file_name}", local_file.write)
            print(f"{file_name} downloaded from FTP for {ftp_user}.")
        

            if supplier_name == 'Lipsey':
                process_lipsey(os.path.join(update_dir, file_name), userid)

            elif supplier_name == 'SSI':
                process_ssi(os.path.join(update_dir, file_name), userid)

            elif supplier_name == 'Zanders':
                            # Download file from FTP
                with open(os.path.join(update_dir, file2_name), "wb") as local_file:
                    ftp.retrbinary(f"RETR {file2_name}", local_file.write)
                print(f"{file2_name} downloaded from FTP for {ftp_user}.")
                process_zanders(os.path.join(update_dir, file_name), os.path.join(update_dir, file2_name),userid)
                
            elif supplier_name == "CWR":
                process_cwr(os.path.join(update_dir, file_name), userid)


    except Exception as e:
        print(f"Error downloading {file_name} from FTP for {ftp_user}: {e}")
    

# dtype={14: str}
def process_lipsey(file_path, userid):
    try:
        
        df = pd.read_csv(file_path, encoding='latin1')
        update_data = df.set_index('ItemNumber').to_dict('index')
        items_to_update = Lipsey.objects.filter(itemnumber__in=update_data.keys(), user_id = userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0

        
        for item in product_table_update:
            row_data = update_data.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost

                item.total_product_cost = compute_price(row_data.get("Price"), fixed_markup, percentage_markup, shipping_cost)
                item.price = row_data.get("Price")
                item.quantity = row_data.get("Quantity")
                item.map = row_data.get("RetailMap")

        for item in items_to_update:
            row_data = update_data.get(item.itemnumber)
            if row_data:
                item.price = row_data.get("Price")
                item.currentprice = row_data.get("CurrentPrice")
                item.retailmap = row_data.get("RetailMap")
                item.quantity = row_data.get("Quantity")
                item.allocated = row_data.get("Allocated")
                item.onsale = row_data.get("OnSale")
                item.total_product_cost = compute_price(row_data.get("Price"), fixed_markup, percentage_markup, shipping_cost)

        # Bulk update in one query
        Lipsey.objects.bulk_update(items_to_update,  ['price', 'currentprice', 'retailmap', 'total_product_cost' ], batch_size=500)
        print('Lipsey updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'price', 'total_product_cost', 'map'], batch_size=500)
        print('General product table updated successfully For Lipsey.')
        
    except Exception as e:
        print(f"Error processing Lipsey file: {e}")

def process_zanders(file_path, file2_path, userid):
    try:
        df = pd.read_csv(file_path, encoding='latin1')
        df2 = pd.read_csv(file2_path, encoding = 'latin1', dtype={14: str})
        

        update_data = df.set_index('itemnumber').to_dict('index')
        update_data2 = df2.set_index('itemnumber').to_dict('index')

        items_to_update = Zanders.objects.filter(itemnumber__in=update_data.keys(), user_id = userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0

        
        for item in product_table_update:
            row_data = update_data.get(item.sku)
            row_data2 = update_data2.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost

                item.total_product_cost = compute_price(row_data.get("price1"), fixed_markup, percentage_markup, shipping_cost)
                item.price = row_data.get("price1")
                item.quantity = row_data.get("qty1")
                item.map = row_data2.get('mapprice')

        for item in items_to_update:
            row_data = update_data.get(item.itemnumber)
            row_data2 = update_data2.get(item.itemnumber)

            if row_data:
                item.price1 = row_data.get("price1")
                item.qty1 = row_data.get("qty1")
                item.mapprice = row_data2.get("mapprice")
                item.total_product_cost = compute_price(row_data.get("price1"), fixed_markup, percentage_markup, shipping_cost)


        # Bulk update in one query
        Zanders.objects.bulk_update(items_to_update, ['price1', 'qty1', 'mapprice', 'total_product_cost'], batch_size=500)
        print('Zanders updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'price', 'total_product_cost', 'map'], batch_size=500)
        print('General product table updated successfully For Zanders.')

    except Exception as e:
        print(f"Error processing Zanders file: {e}")

def process_ssi(file_path, userid):
    try: 
        df = pd.read_csv(file_path, encoding='latin1')
        update_data = df.set_index('SKU').to_dict('index')
        items_to_update = Ssi.objects.filter(sku__in=update_data.keys(), user_id = userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0
        shipping_cost_avg = False

        for item in product_table_update:
            row_data = update_data.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost
                shipping_cost_avg = item.enrollment.shipping_cost_average
                if shipping_cost_avg:
                    shipping_cost = row_data.get('AVG SHIP COST')

                item.total_product_cost = compute_price(row_data.get("RAPID RETAIL PRICE"), fixed_markup, percentage_markup, shipping_cost)
                item.price = row_data.get("RAPID RETAIL PRICE")
                item.quantity = row_data.get("QTY")
                item.msrp = row_data.get("MSRP")
                item.map = row_data.get("MAP")

        for item in items_to_update:
            row_data = update_data.get(item.sku)
            if row_data:
                item.price = row_data.get("RAPID RETAIL PRICE")
                item.map = row_data.get("MAP")
                item.msrp = row_data.get("MSRP")
                item.avgshipcost = row_data.get("AVG SHIP COST")
                item.qty = row_data.get("QTY")
                if shipping_cost_avg:
                    shipping_cost = row_data.get('AVG SHIP COST')

                item.total_product_cost = compute_price(row_data.get("RAPID RETAIL PRICE"), fixed_markup, percentage_markup, shipping_cost)



        # Bulk update in one query
        Ssi.objects.bulk_update(items_to_update, ['price', 'map', 'msrp', 'avgshipcost', 'qty', 'total_product_cost'], batch_size=500)
        print('SSI updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'price', 'msrp', 'map', 'total_product_cost' ], batch_size=500)
        print('General product table updated successfully For SSI.')

    except Exception as e:
        print(f"Error processing SSI file: {e}")

def process_fragrancex(file_path, userid):
    try:
        df = pd.read_csv(file_path, encoding='latin1')
        update_data = df.set_index('ItemId').to_dict('index')
        items_to_update = Fragrancex.objects.filter(itemId__in=update_data.keys(), user_id = userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0


        for item in product_table_update:
            row_data = update_data.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost

                item.total_product_cost = compute_price(row_data.get("wholesalePriceUSD"), fixed_markup, percentage_markup, shipping_cost)
                item.price = row_data.get("WholesalePriceUSD")
                item.quantity = row_data.get("QuantityAvailable")
                item.msrp = row_data.get("RetailPriceUSD")
                    
        for item in items_to_update:
            row_data = update_data.get(item.itemId)
            if row_data:
                item.retailPriceUSD = row_data.get("RetailPriceUSD")
                item.wholesalePriceUSD= row_data.get("WholesalePriceUSD")
                item.wholesalePriceAUD= row_data.get("WholesalePriceAUD")
                item.wholesalePriceGBP= row_data.get("WholesalePriceGBP")
                item.wholesalePriceCAD= row_data.get("WholesalePriceCAD")
                item.quantityAvailable = row_data.get("QuantityAvailable")
                item.total_product_cost = compute_price(row_data.get("wholesalePriceUSD"), fixed_markup, percentage_markup, shipping_cost)

        # Bulk update in one query
        Fragrancex.objects.bulk_update(items_to_update, ['retailPriceUSD', 'wholesalePriceUSD', 'wholesalePriceAUD', 'wholesalePriceGBP', 'wholesalePriceCAD', 'quantityAvailable', 'total_product_cost'], batch_size=500)
        print('FragranceX updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'price', 'msrp', 'total_product_cost'], batch_size=500)
        print('General product table updated successfully For FragranceX.')
    
    except Exception as e:
        print(f"Error processing FragranceX file: {e}")

def process_cwr(file_path, userid):
    try:
        df = pd.read_csv(file_path, encoding='latin1')
        update_data = df.set_index('sku').to_dict('index')
        items_to_update = Cwr.objects.filter(sku__in=update_data.keys(), user_id = userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0


        for item in product_table_update:
            row_data = update_data.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost

                item.total_product_cost = compute_price(row_data.get("price"), fixed_markup, percentage_markup, shipping_cost)
                item.price = row_data.get("price")
                item.quantity = row_data.get("qty")
                item.map = row_data.get('map')
            
                
        for item in items_to_update:
            row_data = update_data.get(item.sku)
            if row_data:
                item.price = row_data.get("price")
                item.qty = row_data.get("qty")
                item.qtynj = row_data.get("qtynj")
                item.qtyfl = row_data.get("qtyfl")
                item.map = row_data.get('map')
                item.total_product_cost = compute_price(row_data.get("price"), fixed_markup, percentage_markup, shipping_cost)

        # Bulk update in one query
        Cwr.objects.bulk_update(items_to_update, ['price', 'qty', 'qtynj', 'qtyfl', 'map', 'total_product_cost'], batch_size=500)
        print('Cwr updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'price', 'total_product_cost', 'map' ], batch_size=500)
        print('General product table updated successfully For Cwr.')


    except Exception as e:
        print(f"Error reading CWR file: {e}")

def process_rsr(file_path, userid):
    try:
        df = pd.read_csv(file_path, encoding='latin1')

        # Drop duplicate rows, keeping the first occurrence
        df = df.drop_duplicates(subset='SKU', keep='first')

        update_data = df.set_index('SKU').to_dict('index')
        items_to_update = Rsr.objects.filter(sku__in=update_data.keys(), user_id= userid)
        product_table_update = Generalproducttable.objects.filter(sku__in=update_data.keys(), user_id=userid)
        percentage_markup = 0
        fixed_markup = 0
        shipping_cost = 0



        for item in product_table_update:
            row_data = update_data.get(item.sku)
            if row_data:
                percentage_markup = item.enrollment.percentage_markup
                fixed_markup = item.enrollment.fixed_markup
                shipping_cost = item.enrollment.shipping_cost

                item.total_product_cost = compute_price(row_data.get("DealerPrice"), fixed_markup, percentage_markup, shipping_cost)
                item.msrp = row_data.get("MSRP")
                item.quantity = row_data.get("InventoryOnHand")
                item.map = row_data.get("RetailMAP")
                item.price = row_data.get("DealerPrice")

        for item in items_to_update:
            row_data = update_data.get(item.sku)
            if row_data:
                item.msrp = row_data.get("MSRP")
                item.retail_map = row_data.get("RetailMAP")
                item.inventory_on_hand = row_data.get("InventoryOnHand")
                item.dealer_price = row_data.get("DealerPrice")
                item.total_product_cost = compute_price(row_data.get("DealerPrice"), fixed_markup, percentage_markup, shipping_cost)

        # Bulk update in one query
        Rsr.objects.bulk_update(items_to_update, ['msrp', 'retail_map', 'inventory_on_hand', 'dealer_price', 'total_product_cost'], batch_size=500)
        print('RSR updated successfully.')

        Generalproducttable.objects.bulk_update(product_table_update, ['quantity', 'msrp', 'map', "price", 'total_product_cost'], batch_size=500)
        print('General product table updated successfully For Rsr.')


    except Exception as e:
        print(f"Error processing Rsr file: {e}")


# Function to periodically pull updates

def periodic_task(supplier_name,userid, ftp_host='', ftp_user='', ftp_password='', apiAccessId='', apiAccessKey='', username='', password='', pos='I'):
    while True:
        pull_vendor_update(
            supplier_name,
            userid,
            ftp_host,
            ftp_user,
            ftp_password,
            apiAccessId,
            apiAccessKey,
            username,
            password,
            pos
        )
        if supplier_name =='FragranceX':

            time.sleep(10800)  # Wait for 3 hrs
        else:    
         
            time.sleep(300)  # Wait for 5 minutes
            