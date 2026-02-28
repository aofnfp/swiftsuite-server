from vendorActivities.models import Fragrancex, Lipsey, Cwr, Rsr, Ssi, Zanders
from .models import FragrancexUpdate, LipseyUpdate, CwrUpdate, RsrUpdate, ZandersUpdate, Enrollment, BackgroundTask
import os, csv, time
from ftplib import FTP
from vendorActivities.apiSupplier import getFragranceXData, getRSRWithAttr
from .utils import VendorDataMixin
from celery import shared_task, chain
import logging
from inventoryApp.models import InventoryModel
from django.utils import timezone
from django.db.models import Q

mixin = VendorDataMixin()
logger = logging.getLogger(__name__)

@shared_task(queue='heavy-io')
def update_vendor_data(enrollment_id):
    try:
        enrollment = Enrollment.objects.get(id = enrollment_id)
        file_path = None
        
        supplier_name = enrollment.vendor.name.lower()
        file_name = ''
        
        update_dir = os.path.join("update_dir", supplier_name)
        os.makedirs(update_dir, exist_ok=True)

        user_id = enrollment.user.id
        
        if supplier_name == 'fragrancex':
            apiAccessId=enrollment.account.apiAccessId
            apiAccessKey=enrollment.account.apiAccessKey
            data = getFragranceXData(apiAccessId, apiAccessKey)
            file_name = f'fragrancex_{user_id}.csv'
            file_path = os.path.join(update_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                if 'RetailPriceUSD' not in data[3].keys():
                    data[3]['RetailPriceUSD'] = 0
                writer = csv.DictWriter(file, fieldnames=data[3].keys())
                writer.writeheader()
                writer.writerows(data)

                
            print(f"Data successfully written to {file_path}")
            mixin.process_vendor_update(
                file_path,
                enrollment,
                Fragrancex,
                FragrancexUpdate,
                "ItemId",
                "WholesalePriceUSD",
                "QuantityAvailable"
            )
        

        elif supplier_name == 'rsr':
            username=enrollment.account.Username
            password=enrollment.account.Password
            pos=enrollment.account.POS
            try:
                data = getRSRWithAttr(username, password, pos)
                if not data or not isinstance(data, list):
                    raise ValueError("RSR data is empty or invalid")
            except Exception as e:
                raise Exception(f"Failed to fetch RSR data for enrollment {enrollment.id}: {e}")
            
            file_name = f"rsr_{user_id}.csv"
            file_path = os.path.join(update_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

            print(f"Data successfully written to {file_path}")
            mixin.process_vendor_update(
                file_path,
                enrollment,
                Rsr,
                RsrUpdate,
                "SKU",
                "DealerPrice",
                "InventoryOnHand"
            )
            

        else:
            ftp_host=enrollment.account.host
            ftp_user=enrollment.account.ftp_username
            ftp_password=enrollment.account.ftp_password
            port = 21
            
            # Dictionary mapping supplier configurations
            supplier_config = {
                'lipsey': {
                    'file_name': f'pricingquantity_{user_id}.csv',
                    'ftp_path': '/',
                    'process_func': process_lipsey,
                    'extra_files': None,
                    'remote_file': 'pricingquantity.csv'
                },
                'ssi': {
                    'file_name': f'RR_Pricing_Availability_{user_id}.csv',
                    'ftp_path': '/Pricing-Availability',
                    'process_func': process_ssi,
                    'extra_files': None,
                    'remote_file': 'RR_Pricing_Availability.csv'
                },
                'zanders': {
                    'file_name': f'liveinv_{user_id}.csv',
                    'ftp_path': '/Inventory',
                    'process_func': process_zanders,
                    'extra_files': [('zandersinv.csv', f'zandersinv_{user_id}.csv')],
                    'remote_file': 'liveinv.csv'
                },
                'cwr': {
                    'file_name': f'inventory_{user_id}.csv',
                    'ftp_path': '/out',
                    'process_func': process_cwr,
                    'extra_files': None,
                    'remote_file': 'inventory.csv'
                }
            }
            
            # Get configuration for current supplier
            config = supplier_config.get(supplier_name)
            if not config:
                raise ValueError(f"Unsupported supplier: {supplier_name}")
            
            ftp = None
            file_path = None
            extra_file_paths = []
            
            try:
                # FTP connection
                ftp = FTP()
                ftp.connect(ftp_host, port)
                ftp.login(user=ftp_user, passwd=ftp_password)
                ftp.set_pasv(True)
                ftp.cwd(config['ftp_path'])
                
                # Download main file from FTP
                file_path = os.path.join(update_dir, config['file_name'])
                with open(file_path, "wb") as local_file:
                    ftp.retrbinary(f"RETR {config['remote_file']}", local_file.write)
                    
                print(f"{config['file_name']} downloaded from FTP for {ftp_user}.")
                
                # Download extra files if any
                if config['extra_files']:
                    for remote_file, local_name in config['extra_files']:
                        extra_path = os.path.join(update_dir, local_name)
                        with open(extra_path, "wb") as local_file:
                            ftp.retrbinary(f"RETR {remote_file}", local_file.write)
                            
                        print(f"{local_name} downloaded from FTP for {ftp_user}.")
                        extra_file_paths.append(extra_path)
                
                # Process the files
                if extra_file_paths:
                    config['process_func'](file_path, *extra_file_paths, enrollment)
                else:
                    config['process_func'](file_path, enrollment)
                    
            finally:
                # Clean up files
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                    
                for extra_path in extra_file_paths:
                    if os.path.exists(extra_path):
                        os.remove(extra_path)
                        print(f"Deleted file: {extra_path}")
                
                if ftp:
                    ftp.quit()
                    
    except Exception as e:
        print(f"Error updating enrollment {enrollment.id}: {e}")

    finally:
        # Clean up
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
            
    return enrollment_id

def process_lipsey(file_path, enrollment):
    mixin.process_vendor_update(
        file_path,
        enrollment,
        Lipsey,
        LipseyUpdate,
        "ItemNumber",
        "Price",
        "Quantity"
    )
    
def process_ssi(file_path, enrollment):
    pass

def process_zanders(file_path, file2_path, enrollment):
    mixin.process_vendor_update(
        file_path,
        enrollment,
        Zanders,
        ZandersUpdate,
        "itemnumber",
        'price1',
        'available'
    )

def process_cwr(file_path, enrollment):
    mixin.process_vendor_update(
        file_path,
        enrollment,
        Cwr,
        CwrUpdate,
        "sku",
        'price',
        'qty'
    )


@shared_task(queue='heavy-io')
def update_all_enrollments():
    tasks = BackgroundTask.objects.all()
    for task in tasks:
        try:
            enrollment = task.enrollment
            logger.info(f"Processing enrollment {enrollment.identifier}")
            chain(
                update_vendor_data.s(enrollment.id),
                update_inventory.s()
            ).delay()
            task.processed = True
            task.result = "Success"
        except Exception as e:
            task.processed = False
            task.result = f"Error: {str(e)}"
            logger.error(task.result)
        finally:
            task.save()


def to_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except:
        return default

        
@shared_task(queue='default')        
def update_inventory(enrollment_id):
    enrollment = Enrollment.objects.get(id=enrollment_id)
    logger.info(f"Updating inventory for enrollment {enrollment_id}-{enrollment.identifier}")

    shipping_cost = to_float(enrollment.shipping_cost)
    fixed_markup = to_float(enrollment.fixed_markup)
    percentage_markup = to_float(enrollment.percentage_markup)
    stock_minimum = enrollment.stock_minimum or 0
    
    vendor_name = enrollment.vendor.name.lower()
    inventory_items = InventoryModel.objects.filter(product__enrollment=enrollment)
    total_items = inventory_items.count()
    updated_count = 0
    skipped_count = 0

    inventory_to_update = []
    general_products_to_update = []
    BATCH_SIZE = 500

    for item in inventory_items:

        if vendor_name == 'fragrancex':
            product = FragrancexUpdate.objects.filter(sku=item.sku, enrollment=enrollment).first()
        elif vendor_name == 'rsr':
            product = RsrUpdate.objects.filter(sku=item.sku, enrollment=enrollment).first()
        elif vendor_name == 'lipsey':
            product = LipseyUpdate.objects.filter(sku=item.sku, enrollment=enrollment).first()
        elif vendor_name == 'cwr':
            product = CwrUpdate.objects.filter(sku=item.sku, enrollment=enrollment).first()
        elif vendor_name == 'zanders':
            product = ZandersUpdate.objects.filter(sku=item.sku, enrollment=enrollment).first()
        else:
            product = None
            
        if not product:
            skipped_count += 1
            logger.warning(f"Skipped SKU {item.sku} — no matching {vendor_name} update entry for enrollment {enrollment.identifier}")
            continue
        
        price = to_float(product.price)

        total_price = round(
            price + fixed_markup + ((percentage_markup / 100) * price) + shipping_cost,
            2
        )
        
        item.total_product_cost = total_price
        item.shipping_cost = shipping_cost
        item.price = price
        item.map = product.map

        map_value = to_float(product.map)

        item_fixed = to_float(item.fixed_markup)
        item_pct = to_float(item.fixed_percentage_markup)
        item_profit = to_float(item.profit_margin)

        start_price = (
            total_price +
            item_fixed +
            ((item_pct / 100) * total_price) +
            ((item_profit / 100) * total_price)
        )

        if map_value:
            start_price = max(start_price, map_value)

        item.start_price = round(start_price, 2)

        # If vendor quantity is below the set minimum, render it as 0
        quantity = product.quantity if product.quantity >= stock_minimum else 0
        item.quantity = quantity
        item.last_updated = timezone.now()
        inventory_to_update.append(item)

        # Keep Generalproducttable in sync so the 8-hour
        # update_inventory_price_quantity_task reads fresh data
        general_product = item.product  # FK to Generalproducttable
        if general_product:
            general_product.quantity = quantity
            general_product.price = price
            general_product.total_product_cost = total_price
            general_product.map = product.map
            general_products_to_update.append(general_product)
        
        updated_count += 1

    # Flush all changes in batches
    if inventory_to_update:
        try:
            InventoryModel.objects.bulk_update(
                inventory_to_update,
                ['total_product_cost', 'shipping_cost', 'price', 'start_price', 'quantity', 'last_updated', 'map'],
                batch_size=BATCH_SIZE
            )
        except Exception as e:
            logger.error(f"Bulk update failed for InventoryModel: {e}. Falling back to individual saves.")
            for item in inventory_to_update:
                try:
                    item.save(update_fields=['total_product_cost', 'shipping_cost', 'price', 'start_price', 'quantity', 'last_updated', 'map'])
                except Exception as individual_e:
                    logger.error(f"Failed to save individual item {item.sku}: {individual_e}")

    if general_products_to_update:
        from .models import Generalproducttable
        try:
            Generalproducttable.objects.bulk_update(
                general_products_to_update,
                ['quantity', 'price', 'total_product_cost', 'map'],
                batch_size=BATCH_SIZE
            )
        except Exception as e:
            logger.error(f"Bulk update failed for Generalproducttable: {e}. Falling back to individual saves.")
            for gp in general_products_to_update:
                try:
                    gp.save(update_fields=['quantity', 'price', 'total_product_cost', 'map'])
                except Exception as individual_e:
                     logger.error(f"Failed to save individual general product {gp.sku}: {individual_e}")

    logger.info(f"Inventory sync for {enrollment.identifier}: {updated_count}/{total_items} updated, {skipped_count} skipped (no update entry)")
