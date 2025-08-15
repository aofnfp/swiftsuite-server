from vendorActivities.models import Fragrancex, Lipsey, Cwr, Rsr, Ssi, Zanders
from .models import FragrancexUpdate, LipseyUpdate, CwrUpdate, RsrUpdate, ZandersUpdate, Enrollment
import os, csv, time
from ftplib import FTP
from vendorActivities.apiSupplier import getFragranceXData, getRSR
from .utils import VendorDataMixin

mixin = VendorDataMixin()

def update_vendor_data(enrollment):
    try:
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
                data = getRSR(username, password, pos)
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


def update_all_enrollments():
    from vendorEnrollment.models import Enrollment
    for enrollment in Enrollment.objects.all():
        update_vendor_data(enrollment)


def update_func(enrollment_id):
    while True:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        supplier_name = enrollment.vendor.name.lower()
        update_vendor_data(enrollment)
        if supplier_name == 'fragrancex':
            time.sleep(1080)
        else:
            time.sleep(600)