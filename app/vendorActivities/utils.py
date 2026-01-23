import pandas as pd # type: ignore
from .models import Fragrancex, Lipsey, Cwr, Zanders, Rsr
import re, json, os, csv, time
from .apiSupplier import getFragranceXData, getRSR, getRSRWithAttr
from ftplib import FTP
from django.utils import timezone
from PIL import Image
import requests
from io import BytesIO



def get_suppliers_for_vendor(vendor_name:str, ftp_host, ftp_user, ftp_password):
    if vendor_name is None:
        raise ValueError("Vendor name must be provided")
    
    vendor_name = vendor_name.lower()

    if vendor_name == 'zanders':
        return [
            (vendor_name, ftp_host, ftp_user, ftp_password, "/Inventory", "itemimagelinks.csv", 1, 21),
            (vendor_name, ftp_host, ftp_user, ftp_password, "/Inventory", "zandersinv.csv", 2, 21),
            (vendor_name, ftp_host, ftp_user, ftp_password, "/Inventory", "detaildesctext.csv", 3, 21),
        ]
    elif vendor_name == 'cwr':
        return [
            (vendor_name, ftp_host, ftp_user, ftp_password, "/out", "catalog.csv", 1, 21),
            (vendor_name, ftp_host, ftp_user, ftp_password, "/out", "inventory.csv", 2, 21)
        ]
    elif vendor_name == 'lipsey':
        return [(vendor_name, ftp_host, ftp_user, ftp_password, "/", "catalog.csv", 1, 21)]
    elif vendor_name == 'ssi':
        return [(vendor_name, ftp_host, ftp_user, ftp_password, "/Products", "RR_Products.csv", 1, 21)]



class VendorActivity():
    def __init__(self):
        self.data = pd.DataFrame()
        self.insert_data = []
        self.file_paths= []
        self.filter_values = dict()
        self.justTest = False
        

    def removeFile(self):
        for file in self.file_paths:
            if os.path.exists(file):
                os.remove(file)
                self.file_paths = []
                print("File removed")
            else:
                print("File does not exist")
    
    def clean_text(self, text):
        # Use str.translate for better efficiency
        translation_table = str.maketrans({
            "‘": "'", "’": "'", "“": '"', "”": '"', 
            "–": "-", "—": "-", "…": "...",
            "\u00A0": " "
        })
        text = text.translate(translation_table)
        
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def main(self, suppliers:tuple|list[tuple]):
        try:
            if isinstance(suppliers[0], str) and suppliers[0] in ['fragrancex', 'rsr']:
                value = self.process_supplier(suppliers)

            else:
                for supplier in suppliers:
                    value = self.process_supplier(supplier)
                    
            return value
        except Exception as e:
            print(f"Error: {e}")
            return None

    def process_supplier(self, supplier):
        """Process each supplier."""
   
        supplier_name, *_ = supplier

        print(f"Processing {supplier_name}...")
        local_dir = os.path.join("local_dir", supplier_name)
        os.makedirs(local_dir, exist_ok=True)
        try:
            value = self.download_csv_from_ftp(supplier, local_dir)
            print(f"{supplier_name} data processed successfully.")
            return value
        except Exception as e:
            print(f"Error processing {supplier_name}: {str(e)}")
            
    def download_csv_from_ftp(self, supplier, local_dir=".", port=21):
        """Download CSV file from FTP server."""
        
        if supplier[0] == 'fragrancex':
            supplier_name, apiAccessId, apiAccessKey = supplier
            data = getFragranceXData(apiAccessId, apiAccessKey)
            file_name = "fragrancex.csv"
            file_path = os.path.join(local_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                # Create a writer object
                if 'RetailPriceUSD' not in data[3].keys():
                    data[3]['RetailPriceUSD'] = 0
                writer = csv.DictWriter(file, fieldnames=data[3].keys())
                writer.writeheader()
                # Write the data
                writer.writerows(data)
            
            self.file_paths.append(file_path)
            print(f"Data successfully written to {file_path}")
            
            value = self.process_csv(supplier_name, local_dir, file_name)
            return value

        elif supplier[0] == 'rsr':
            supplier_name, Username, Password, POS = supplier
            
            if self.justTest:
                data = getRSR(Username, Password, POS)
            else:
                data = getRSRWithAttr(Username, Password, POS)
            
            print(len(data), "final length")
            file_name = "rsr.csv"
            file_path = os.path.join(local_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            
            self.file_paths.append(file_path)
            print(f"Data successfully written to {file_path}")
            value = self.process_csv(supplier_name, local_dir, file_name)
            return value

        else:
            supplier_name, ftp_host, ftp_user, ftp_password, ftp_path, file_name, index, port = supplier
            file_path = os.path.join(local_dir, file_name)
            ftp = FTP()
            ftp.connect(ftp_host, port)
            ftp.login(user=ftp_user, passwd=ftp_password)
            ftp.set_pasv(True)
            ftp.cwd(ftp_path)
            with open(file_path, "wb") as local_file:
                ftp.retrbinary(f"RETR {file_name}", local_file.write)
        
            print(f"{file_name} downloaded from FTP for {ftp_user}.")
            self.file_paths.append(file_path)
            value = self.process_csv(supplier_name, local_dir, file_name, index)
            return value

    def process_csv(self, supplier_name, local_dir, file_name, index=None):
        with open(os.path.join(local_dir, file_name), "r", encoding='latin1') as file:
            csv_data = csv.DictReader(file)
            
            
            if supplier_name == "fragrancex":
                self.filter_values = self.filters_fragranceX(csv_data)
                if self.justTest:
                    return self.filter_values
                
                value = self.process_fragranceX()    
                return value
            
            elif supplier_name == "lipsey":
                self.filter_values = self.filters_lipsey(csv_data)
                if self.justTest:
                    return self.filter_values
                
                value = self.process_lipsey()
                return value
                
            elif supplier_name == "cwr":
                self.filter_values = self.filters_cwr(csv_data, index)
                if index == 2:
                    if self.justTest:
                        return self.filter_values
  
                    value = self.process_cwr()
                    return value 
                
                return {}
            
            elif supplier_name == 'zanders':
                self.filter_values = self.filters_zanders(csv_data, index)
                if index == 3:
                    if self.justTest:
                        return self.filter_values
                    
                    value = self.process_zanders()
                    return value
                return {}
            elif supplier_name == 'rsr':
                self.filter_values = self.filters_rsr(csv_data)
                if self.justTest:
                    return self.filter_values
                value = self.process_rsr()
                return value
                    
                
    def filters_rsr(self, csv_data):
        items = []
        for row in csv_data:
            items.append(row)
            
        self.data = pd.DataFrame(items)
        
        category = self.data['CategoryName'].unique()
        manufacturer = self.data['ManufacturerName'].unique()
        shippable = self.data['DropShippable'].unique()

        category_dictList = []
        manufacturer_dictList = []
        shippable_dictList = []
        x = 1
        for value in category:
            _dict = {"id":x, "label":value, "checked":False}
            category_dictList.append(_dict)
            x+=1
        y = 1
        for value in manufacturer:
            _dict = {"id":y, "label":value, "checked":False}
            manufacturer_dictList.append(_dict)
            y+=1
        
        z = 1
        for value in shippable :
            _dict = {"id":z, "label":value, "checked":False}
            shippable_dictList.append(_dict)
            z+=1

        filter_values = {'category':category_dictList, 'manufacturer':manufacturer_dictList, 'shippable':shippable_dictList}
        return filter_values              
                
    def filters_fragranceX(self, csv_data):
        items = []
        for row in csv_data:
            items.append(row)
            
        self.data = pd.DataFrame(items)
        brand = self.data['BrandName'].unique()
        brand_dictList = []
        for x, value in enumerate(brand, start=1):
            brand_dictList.append({"id": x, "label": value, "checked": False})

        filter_values = {'brand': brand_dictList}
        return filter_values
    
    def filters_lipsey(self, csv_data):
        items = []
        for row in csv_data:
            items.append(row)
            
        self.data = pd.DataFrame(items)
        productType =self.data['ItemType'].unique()
        manufacturer = self.data['Manufacturer'].unique()
         
        manufacturer_dictList = []
        productType_dictList = []
        x = 1
        for value in productType:
            _dict = {"id":x, "label":value, "checked":False}
            productType_dictList.append(_dict)
            x+=1

        y = 1
        for value in manufacturer:
            _dict = {"id":y, "label":value, "checked":False}
            manufacturer_dictList.append(_dict)
            y+=1

        filter_values = {'productType':productType_dictList, 'manufacturer':manufacturer_dictList}

        return filter_values
     
    def filters_cwr(self, csv_data, index):
        items = []
        for row in csv_data:
            items.append(row)
            
        if index == 1:
            self.data = pd.DataFrame(items)
        elif index == 2:
            data2 = pd.DataFrame(items)
            self.data = self.data.merge(data2, left_on="CWR Part Number", right_on="sku")  
        
        return {}

    def filters_zanders(self, csv_data, index):
        items = []
        itemNumber = []
        description = []

        for row in csv_data:
            if index == 3:
                itemNumber.append(str(row).split("~")[1].split(":")[1].replace("'", "").strip())
                description.append(str(row).split("~")[2].replace("}", ""))
            else:
                items.append(row)

        if index == 3:
            data2 = pd.DataFrame({"Itemnumber": itemNumber, "description": description})
            self.data = self.data.merge(data2, left_on="itemnumber", right_on="Itemnumber")
            
            manufacturer = self.data['manufacturer'].unique()
            manufacturer_dictList = []
            for x, value in enumerate(manufacturer, start=1):
                manufacturer_dictList.append({"id": x, "label": value, "checked": False})
            filter_values = {'manufacturer': manufacturer_dictList}

            return filter_values

        elif index == 2:
            data2 = pd.DataFrame(items)
            self.data = self.data.merge(data2, left_on="ItemNumber", right_on="itemnumber")

        else:
            self.data = pd.DataFrame(items)

        return {}
     
     
    def process_fragranceX(self):
        try:
            self.insert_data = []

            for row in self.data.itertuples(index=False):
                
                description = self.clean_text(getattr(row, "Description", ""))
                brand_name = self.clean_text(getattr(row, "BrandName", ""))
                product_type = getattr(row, "Type", "")
                gender = getattr(row, "Gender", "")
                size = getattr(row, "Size", "")
                metric_size = getattr(row, "MetricSize", "")

                product_name = (
                    f"{row.ProductName} by {brand_name} "
                    f"{product_type} {size} for {gender}"
                ).strip()

                features = [
                    {"name": "Brand", "value": brand_name},
                    {"name": "Gender", "value": gender},
                    {"name": "Size", "value": size},
                    {"name": "Metric Size", "value": metric_size},
                    {"name": "Product Type", "value": product_type},
                ]

                fx_product = Fragrancex(
                    sku=row.ItemId,
                    productName=product_name,
                    description=description,
                    brandName=brand_name,
                    gender=gender,
                    size=size,
                    metric_size=metric_size,
                    retailPriceUSD=getattr(row, "RetailPriceUSD", 0),
                    wholesalePriceUSD=getattr(row, "WholesalePriceUSD", 0),
                    wholesalePriceEUR=getattr(row, "WholesalePriceEUR", 0),
                    wholesalePriceGBP=getattr(row, "WholesalePriceGBP", 0),
                    wholesalePriceCAD=getattr(row, "WholesalePriceCAD", 0),
                    wholesalePriceAUD=getattr(row, "WholesalePriceAUD", 0),
                    smallImageUrl=getattr(row, "SmallImageUrl", ""),
                    largeImageUrl=getattr(row, "LargeImageUrl", ""),
                    type=product_type,
                    quantityAvailable=getattr(row, "QuantityAvailable", 0),
                    upc=getattr(row, "Upc", ""),
                    instock=getattr(row, "Instock", False),
                    parentCode=getattr(row, "ParentCode", ""),
                    features=json.dumps(features),
                )

                self.insert_data.append(fx_product)

            if not self.insert_data:
                return True

            # Insert new products only
            Fragrancex.objects.bulk_create(
                self.insert_data,
                batch_size=500,
                ignore_conflicts=True
            )

            # Fetch existing rows for update
            skus = [obj.sku for obj in self.insert_data]
            existing = {
                obj.sku: obj
                for obj in Fragrancex.objects.filter(sku__in=skus)
            }

            to_update = []

            for obj in self.insert_data:
                if obj.sku in existing:
                    db_obj = existing[obj.sku]
                    db_obj.size = obj.size
                    db_obj.retailPriceUSD = obj.retailPriceUSD
                    db_obj.wholesalePriceUSD = obj.wholesalePriceUSD
                    db_obj.wholesalePriceEUR = obj.wholesalePriceEUR
                    db_obj.wholesalePriceGBP = obj.wholesalePriceGBP
                    db_obj.wholesalePriceCAD = obj.wholesalePriceCAD
                    db_obj.wholesalePriceAUD = obj.wholesalePriceAUD
                    db_obj.quantityAvailable = obj.quantityAvailable
                    db_obj.features = obj.features
                    to_update.append(db_obj)

            if to_update:
                Fragrancex.objects.bulk_update(
                    to_update,
                    fields=[
                        "size",
                        "retailPriceUSD",
                        "wholesalePriceUSD",
                        "wholesalePriceEUR",
                        "wholesalePriceGBP",
                        "wholesalePriceCAD",
                        "wholesalePriceAUD",
                        "quantityAvailable",
                        "features",
                    ],
                    batch_size=500
                )

            print("FragranceX products uploaded successfully")
            return True

        except Exception as e:
            print(f"FragranceX processing failed: {e}")
            return False
        
    def process_lipsey(self):
        try:
            self.insert_data = []

            for row in self.data.itertuples(index=False):
                features = [
                    {"name": "Model", "value": row.Model},
                    {"name": "CaliberGauge", "value": row.CaliberGauge},
                    {"name": "Manufacturer", "value": row.Manufacturer},
                    {"name": "Type", "value": row.Type},
                    {"name": "Action", "value": row.Action},
                    {"name": "BarrelLength", "value": row.BarrelLength},
                    {"name": "Capacity", "value": row.Capacity},
                    {"name": "Finish", "value": row.Finish},
                    {"name": "OverallLength", "value": row.OverallLength},
                    {"name": "Receiver", "value": row.Receiver},
                    {"name": "Safety", "value": row.Safety},
                    {"name": "Sights", "value": row.Sights},
                    {"name": "StockFrameGrips", "value": row.StockFrameGrips},
                    {"name": "Magazine", "value": row.Magazine},
                    {"name": "Weight", "value": row.Weight},
                    {"name": "Chamber", "value": row.Chamber},
                    {"name": "RateOfTwist", "value": row.RateOfTwist},
                    {"name": "ItemType", "value": row.ItemType},
                    {"name": "CountryOfOrigin", "value": row.CountryOfOrigin},
                ]

                product = Lipsey(
                    sku=row.ItemNo,
                    description1=row.Description1,
                    description2=row.Description2,
                    upc=row.Upc,
                    manufacturermodelno=row.ManufacturerModelNo,
                    msrp=row.Msrp,
                    model=row.Model,
                    calibergauge=row.CaliberGauge,
                    manufacturer=row.Manufacturer,
                    type=row.Type,
                    action=row.Action,
                    barrellength=row.BarrelLength,
                    capacity=row.Capacity,
                    finish=row.Finish,
                    overalllength=row.OverallLength,
                    receiver=row.Receiver,
                    safety=row.Safety,
                    sights=row.Sights,
                    stockframegrips=row.StockFrameGrips,
                    magazine=row.Magazine,
                    weight=row.Weight,
                    imagename=f"https://www.lipseyscloud.com/images/{row.ImageName}",
                    chamber=row.Chamber,
                    drilledandtapped=row.DrilledAndTapped,
                    rateoftwist=row.RateOfTwist,
                    itemtype=row.ItemType,
                    additionalfeature1=row.AdditionalFeature1,
                    additionalfeature2=row.AdditionalFeature2,
                    additionalfeature3=row.AdditionalFeature3,
                    shippingweight=row.ShippingWeight,
                    boundbookmanufacturer=row.BoundBookManufacturer,
                    boundbookmodel=row.BoundBookModel,
                    boundbooktype=row.BoundBookType,
                    exclusive=row.Exclusive,
                    quantity=row.Quantity,
                    allocated=row.Allocated,
                    onsale=row.OnSale,
                    price=row.Price,
                    currentprice=row.CurrentPrice,
                    map=row.RetailMap,
                    fflrequired=row.FflRequired,
                    sotrequired=row.SotRequired,
                    exclusivetype=row.ExclusiveType,
                    scopecoverincluded=row.ScopeCoverIncluded,
                    special=row.Special,
                    sightstype=row.SightsType,
                    case=row.Case,
                    family=row.Family,
                    packagelength=row.PackageLength,
                    packagewidth=row.PackageWidth,
                    packageheight=row.PackageHeight,
                    itemgroup=row.ItemGroup,
                    features=json.dumps(features),
                )

                self.insert_data.append(product)

            if not self.insert_data:
                return True

            # Insert new SKUs
            Lipsey.objects.bulk_create(
                self.insert_data,
                batch_size=500,
                ignore_conflicts=True
            )

            # Fetch existing rows for update
            skus = [obj.sku for obj in self.insert_data]
            existing = {
                obj.sku: obj
                for obj in Lipsey.objects.filter(sku__in=skus)
            }

            to_update = []

            for obj in self.insert_data:
                if obj.sku in existing:
                    db_obj = existing[obj.sku]
                    db_obj.quantity = obj.quantity
                    db_obj.allocated = obj.allocated
                    db_obj.price = obj.price
                    db_obj.currentprice = obj.currentprice
                    db_obj.map = obj.map
                    db_obj.features = obj.features
                    to_update.append(db_obj)

            if to_update:
                Lipsey.objects.bulk_update(
                    to_update,
                    fields=[
                        "quantity",
                        "allocated",
                        "price",
                        "currentprice",
                        "map",
                        "features",
                    ],
                    batch_size=500
                )

            print("Lipsey upload completed successfully")
            return True

        except Exception as e:
            print(f"Lipsey processing failed: {e}")
            return False

    def process_cwr(self):
        try:
            self.insert_data = []

            for _, row in self.data.iterrows():

                features = [
                    {"Name": "Quick Specs", "Value": row["Quick Specs"]},
                    {"Name": "Shipping Weight", "Value": row["Shipping Weight"]},
                    {"Name": "Box Height", "Value": row["Box Height"]},
                    {"Name": "Box Length", "Value": row["Box Length"]},
                    {"Name": "Box Width", "Value": row["Box Width"]},
                    {"Name": "Remanufactured", "Value": row["Remanufactured"]},
                    {"Name": "Harmonization Code", "Value": row["Harmonization Code"]},
                    {"Name": "Country Of Origin", "Value": row["Country Of Origin"]},
                    {"Name": "Google Merchant Category", "Value": row["Google Merchant Category"]},
                    {"Name": "Prop 65", "Value": row["Prop 65"]},
                ]

                self.insert_data.append(
                    Cwr(
                        cwr_part_number=row["CWR Part Number"],
                        manufacturer_part_number=row["Manufacturer Part Number"],
                        upc=row["UPC Code"],
                        quantity_available_to_ship_combined=row["Quantity Available to Ship (Combined)"],
                        quantity_available_to_ship_nj=row["Quantity Available to Ship (NJ)"],
                        quantity_available_to_ship_fl=row["Quantity Available to Ship (FL)"],
                        your_cost=row["Your Cost"] if "Your Cost" in row else None,
                        list_price=row["List Price"] if "List Price" in row else None,
                        m_a_p_price=row["MAP Price"] if "MAP Price" in row else None,
                        m_r_p_price=row["MRP Price"] if "MRP Price" in row else None,
                        title=self.clean_text(row["Title"]),
                        manufacturer_name=row["Manufacturer Name"],
                        shipping_weight=row["Shipping Weight"],
                        box_height=row["Box Height"],
                        box_length=row["Box Length"],
                        box_width=row["Box Width"],
                        quick_specs=self.clean_text(row["Quick Specs"]),
                        image_300x300_url=row["Image (300x300) Url"],
                        image_1000x1000_url=row["Image (1000x1000) Url"],
                        exportable=row["Exportable"],
                        oversized=row["Oversized"],
                        remanufactured=row["Remanufactured"],
                        closeout=row["Closeout"],
                        harmonization_code=row["Harmonization Code"],
                        country_of_origin=row["Country Of Origin"],
                        sale=row["Sale"],
                        rebate=row["Rebate"],
                        google_merchant_category=row["Google Merchant Category"],
                        prop_65=row["Prop 65"],
                        returnable=row["Returnable"],
                        sku=row["sku"],
                        mfgn=row["mfgn"],
                        qty=row["qty"],
                        qtynj=row["qtynj"],
                        qtyfl=row["qtyfl"],
                        price=row["price"],
                        map=row["map"],
                        mrp=row["mrp"],
                        features=json.dumps(features),
                    )
                )

            if self.insert_data:
                # Insert new records
                Cwr.objects.bulk_create(
                    self.insert_data,
                    batch_size=300,
                    ignore_conflicts=True
                )

                # Update existing ones
                skus = [obj.sku for obj in self.insert_data]

                existing = {
                    obj.sku: obj
                    for obj in Cwr.objects.filter(sku__in=skus)
                }

                to_update = []

                for obj in self.insert_data:
                    if obj.sku in existing:
                        db_obj = existing[obj.sku]
                        db_obj.qty = obj.qty
                        db_obj.qtynj = obj.qtynj
                        db_obj.qtyfl = obj.qtyfl
                        db_obj.price = obj.price
                        db_obj.map = obj.map
                        db_obj.mrp = obj.mrp
                        to_update.append(db_obj)

                if to_update:
                    Cwr.objects.bulk_update(
                        to_update,
                        fields=["qty", "qtynj", "qtyfl", "price", "map", "mrp"],
                        batch_size=300
                    )

            print("CWR upload completed successfully.")
            return True

        except Exception as e:
            print(f"Error processing CWR data: {e}")
            return False


        
    def process_zanders(self):
        try:
            self.insert_data = []
            
            for _ , items in self.data.iterrows():
        
                features = [
                    {"name": "Weight", "value": items['weight']},
                ]
                
                zanders_product = Zanders(
                    available=items['available'],
                    category=items['category'],
                    desc1=items['desc1'],
                    desc2=items['desc2'],
                    sku=items['itemnumber'],
                    manufacturer=items['manufacturer'],
                    mfgpnumber=items['mfgpnumber'],
                    msrp=items['msrp'],
                    price1=items['price1'],
                    price2=items['price2'],
                    price3=items['price3'],
                    qty1=items['qty1'],
                    qty2=items['qty2'],
                    qty3=items['qty3'],
                    upc=items['upc'],
                    weight=items['weight'],
                    serialized=items['serialized'],
                    map=items['mapprice'],
                    imagelink=items['ImageLink'],
                    description=items["description"],
                    features=json.dumps(features),
                )

                # Add to the batch for bulk processing
                self.insert_data.append(zanders_product)
            
            if self.insert_data:
                Zanders.objects.bulk_create(
                    self.insert_data,
                    batch_size=500,
                    ignore_conflicts=True
                )
                
                 # Update existing ones
                skus = [obj.sku for obj in self.insert_data]

                existing = {
                    obj.sku: obj
                    for obj in Zanders.objects.filter(sku__in=skus)
                }

                to_update = []
                
                for obj in self.insert_data:
                    if obj.sku in existing:
                        db_obj = existing[obj.sku]
                        db_obj.price1 = obj.price1
                        db_obj.price2 = obj.price2
                        db_obj.price3 = obj.price3
                        db_obj.qty1 = obj.qty1
                        db_obj.qty2 = obj.qty2
                        db_obj.qty3= obj.qty3
                        db_obj.map = obj.map
                        to_update.append(db_obj)

                if to_update:
                    Zanders.objects.bulk_update(
                            to_update,
                            batch_size=500,
                            fields=[
                                "price1",
                                "price2",
                                "price3",
                                "qty1",
                                "qty2",
                                "qty3",
                                "map"
                            ],
                        )
            print("Zanders upload completed successfully.")

            return True

        except Exception as e:
            print(f"An error occurred: {e}")
            return e
        
    def process_rsr(self):
        try:
            self.insert_data = []

            for row in self.data.itertuples(index=False):
                # Safe datetime parsing
                last_modified = pd.to_datetime(
                    row.LastModified, errors="coerce"
                )
                if last_modified is not None:
                    last_modified = last_modified.to_pydatetime()
                    if timezone.is_naive(last_modified):
                        last_modified = timezone.make_aware(
                            last_modified,
                            timezone.get_current_timezone()
                        )

                # Build image URLs (no validation here)
                images = [
                    f"https://img.rsrgroup.com/highres-pimages/{row.SKU}_1_HR.jpg"
                ]

                try:
                    rsr_product = Rsr(
                        sku=row.SKU,
                        last_modified=last_modified,
                        upc=row.UPC,
                        title=row.Title,
                        description=row.Description,
                        manufacturer_code=row.ManufacturerCode,
                        manufacturer_name=row.ManufacturerName,
                        manufacturer_part_number=row.ManufacturerPartNumber,
                        department_id=row.DepartmentId,
                        department_name=row.DepartmentName,
                        category_id=row.CategoryId,
                        category_name=row.CategoryName,
                        subcategory_name=row.SubcategoryName,
                        exclusive=row.Exclusive,
                        talo_exclusive=row.TaloExclusive,
                        coming_soon=row.ComingSoon,
                        new_item=row.NewItem,
                        le_resale_only=row.LEResaleOnly,
                        unit_of_measure=row.UnitOfMeasure,
                        items_per_case=row.ItemsPerCase,
                        items_per_unit=row.ItemsPerUnit,
                        units_per_case=row.UnitsPerCase,
                        nfa=row.NFA,
                        hazard_warning=row.HazardWarning,
                        image_count=row.ImageCount,
                        msrp=row.MSRP,
                        map=row.RetailMAP,
                        inventory_on_hand=row.InventoryOnHand,
                        ground_only=row.GroundOnly,
                        drop_ship_block=row.DropShipBlock,
                        closeout=row.Closeout,
                        allocated=row.Allocated,
                        drop_shippable=row.DropShippable,
                        unit_weight=row.UnitWeight,
                        unit_length=row.UnitLength,
                        unit_width=row.UnitWidth,
                        unit_height=row.UnitHeight,
                        case_weight=row.CaseWeight,
                        case_length=row.CaseLength,
                        case_width=row.CaseWidth,
                        case_height=row.CaseHeight,
                        blemished=row.Blemished,
                        dealer_price=row.DealerPrice,
                        dealer_case_price=row.DealerCasePrice,
                        features=json.dumps(row.Attributes),
                        images=json.dumps(images),
                    )

                    self.insert_data.append(rsr_product)

                except Exception as e:
                    print(f"RSR SKU {row.SKU} failed: {e}")
                    continue

            if self.insert_data:
                # Insert new rows
                Rsr.objects.bulk_create(
                    self.insert_data,
                    batch_size=500,
                    ignore_conflicts=True
                )

                # Fetch existing rows for update
                skus = [obj.sku for obj in self.insert_data]
                existing = {
                    obj.sku: obj
                    for obj in Rsr.objects.filter(sku__in=skus)
                }

                to_update = []

                for obj in self.insert_data:
                    if obj.sku in existing:
                        db_obj = existing[obj.sku]
                        db_obj.last_modified = obj.last_modified
                        db_obj.inventory_on_hand = obj.inventory_on_hand
                        db_obj.allocated = obj.allocated
                        db_obj.dealer_price = obj.dealer_price
                        db_obj.dealer_case_price = obj.dealer_case_price
                        to_update.append(db_obj)

                if to_update:
                    Rsr.objects.bulk_update(
                        to_update,
                        fields=[
                            "last_modified",
                            "inventory_on_hand",
                            "allocated",
                            "dealer_price",
                            "dealer_case_price",
                        ],
                        batch_size=500
                    )

            print("RSR products uploaded successfully")
            return True

        except Exception as e:
            print(f"RSR processing failed: {e}")
            return False
