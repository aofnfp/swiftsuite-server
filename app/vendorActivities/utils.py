import pandas as pd
from .models import Fragrancex, Lipsey, Cwr, Zanders, Rsr
import re, json, os, csv, time
from .apiSupplier import getFragranceXData, getRSR, getRsrItemAttribute
from ftplib import FTP
from django.utils import timezone



def get_suppliers_for_vendor(vendor_name:str, ftp_host, ftp_user, ftp_password):
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

    def main(self, suppliers):
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
            data = getRSR(Username, Password, POS)
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
            for _, row in self.data.iterrows():
            
                description = self.clean_text(row.get("Description", ""))
                productName = row.get("ProductName", "")
                sku = row.get("ItemId", "")
                brandName = self.clean_text(row.get("BrandName", ""))
                gender = row.get("Gender", "")
                size =  row.get("Size", "")
                metric_size = row.get("MetricSize", "")
                retailPriceUSD = row.get("RetailPriceUSD", 0)
                wholesalePriceUSD =  row.get("WholesalePriceUSD", 0)
                wholesalePriceEUR = row.get("WholesalePriceEUR", 0)
                wholesalePriceGBP = row.get("WholesalePriceGBP", 0)
                wholesalePriceCAD = row.get("WholesalePriceCAD", 0)
                wholesalePriceAUD =  row.get("WholesalePriceAUD", 0)
                smallImageUrl = row.get("SmallImageUrl", "")
                largeImageUrl = row.get("LargeImageUrl", "")
                productType = row.get("Type", "")
                quantityAvailable = row.get("QuantityAvailable", 0)
                upc = row.get("Upc", "")
                instock = row.get("Instock", False)
                parentCode = row.get("ParentCode", "")
                
                productName = f'{productName} by {brandName} {productType} {size} for {gender}'
                
                features = [
                    {"name": "Brand", "value": brandName},
                    {"name": "Gender", "value": gender},
                    {"name": "Size", "value": size},
                    {"name": "Metric Size", "value": metric_size},
                    {"name": "Product Type", "value": productType},                             
                ]

                # Append processed data to insert list
                self.insert_data.append(Fragrancex(productName=productName, sku=sku, description=description, brandName=brandName, gender=gender, size=size, metric_size=metric_size, retailPriceUSD=retailPriceUSD, wholesalePriceUSD=wholesalePriceUSD, wholesalePriceEUR=wholesalePriceEUR,wholesalePriceGBP=wholesalePriceGBP, wholesalePriceCAD=wholesalePriceCAD, wholesalePriceAUD=wholesalePriceAUD, smallImageUrl=smallImageUrl,largeImageUrl=largeImageUrl, type=productType, quantityAvailable=quantityAvailable,upc=upc, instock=instock, parentCode=parentCode, features = json.dumps(features)))
                
            
            # Insert data into database
            Fragrancex.objects.bulk_create(self.insert_data, batch_size=500, update_conflicts=True, update_fields=["size", "retailPriceUSD", "wholesalePriceUSD", "wholesalePriceEUR", "wholesalePriceGBP", "wholesalePriceCAD", "wholesalePriceAUD", "quantityAvailable",  "features"])
            print('FrangranceX upload successfully')
            
            return True

        except Exception as e:
            return e
        
    def process_lipsey(self):
        try:
            for row in self.data.iterrows():
                row = row[1]

                features = [
                    {"Name": "Model", "Value": row["Model"]},
                    {"Name": "CaliberGauge", "Value": row["CaliberGauge"]},
                    {"Name": "Manufacturer", "Value": row["Manufacturer"]},
                    {"Name": "Type", "Value": row["Type"]},
                    {"Name": "Action", "Value": row["Action"]},
                    {"Name": "BarrelLength", "Value": row["BarrelLength"]},
                    {"Name": "Capacity", "Value": row["Capacity"]},
                    {"Name": "Finish", "Value": row["Finish"]},
                    {"Name": "OverallLength", "Value": row["OverallLength"]},
                    {"Name": "Receiver", "Value": row["Receiver"]},
                    {"Name": "Safety", "Value": row["Safety"]},
                    {"Name": "Sights", "Value": row["Sights"]},
                    {"Name": "StockFrameGrips", "Value": row["StockFrameGrips"]},
                    {"Name": "Magazine", "Value": row["Magazine"]},
                    {"Name": "Weight", "Value": row["Weight"]},
                    {"Name": "Chamber", "Value": row["Chamber"]},
                    {"Name": "DrilledAndTapped", "Value": row["DrilledAndTapped"]},
                    {"Name": "RateOfTwist", "Value": row["RateOfTwist"]},
                    {"Name": "ItemType", "Value": row["ItemType"]},
                    {"Name": "AdditionalFeature1", "Value": row["AdditionalFeature1"]},
                    {"Name": "AdditionalFeature2", "Value": row["AdditionalFeature2"]},
                    {"Name": "AdditionalFeature3", "Value": row["AdditionalFeature3"]},
                    {"Name": "ShippingWeight", "Value": row["ShippingWeight"]},
                    {"Name": "NfaThreadPattern", "Value": row["NfaThreadPattern"]},
                    {"Name": "NfaAttachmentMethod", "Value": row["NfaAttachmentMethod"]},
                    {"Name": "NfaBaffleType", "Value": row["NfaBaffleType"]},
                    {"Name": "SilencerCanBeDisassembled", "Value": row["SilencerCanBeDisassembled"]},
                    {"Name": "SilencerConstructionMaterial", "Value": row["SilencerConstructionMaterial"]},
                    {"Name": "NfaDbReduction", "Value": row["NfaDbReduction"]},
                    {"Name": "SilencerOutsideDiameter", "Value": row["SilencerOutsideDiameter"]},
                    {"Name": "NfaForm3Caliber", "Value": row["NfaForm3Caliber"]},
                    {"Name": "OpticMagnification", "Value": row["OpticMagnification"]},
                    {"Name": "MaintubeSize", "Value": row["MaintubeSize"]},
                    {"Name": "AdjustableObjective", "Value": row["AdjustableObjective"]},
                    {"Name": "ObjectiveSize", "Value": row["ObjectiveSize"]},
                    {"Name": "OpticAdjustments", "Value": row["OpticAdjustments"]},
                    {"Name": "IlluminatedReticle", "Value": row["IlluminatedReticle"]},
                    {"Name": "Reticle", "Value": row["Reticle"]},
                    {"Name": "SightsType", "Value": row["SightsType"]},
                    {"Name": "Choke", "Value": row["Choke"]},
                    {"Name": "DbReduction", "Value": row["DbReduction"]},
                    {"Name": "FinishType", "Value": row["FinishType"]},
                    {"Name": "Frame", "Value": row["Frame"]},
                    {"Name": "GripType", "Value": row["GripType"]},
                    {"Name": "HandgunSlideMaterial", "Value": row["HandgunSlideMaterial"]},
                    {"Name": "CountryOfOrigin", "Value": row["CountryOfOrigin"]},
                    {"Name": "ItemLength", "Value": row["ItemLength"]},
                    {"Name": "ItemWidth", "Value": row["ItemWidth"]},
                    {"Name": "ItemHeight", "Value": row["ItemHeight"]},
                ]
                

                self.insert_data.append(
                    Lipsey(
                        sku=row["ItemNo"],
                        description1=row["Description1"],
                        description2=row["Description2"],
                        upc=row["Upc"],
                        manufacturermodelno=row["ManufacturerModelNo"],
                        msrp=row["Msrp"],
                        model=row["Model"],
                        calibergauge=row["CaliberGauge"],
                        manufacturer=row["Manufacturer"],
                        type=row["Type"],
                        action=row["Action"],
                        barrellength=row["BarrelLength"],
                        capacity=row["Capacity"],
                        finish=row["Finish"],
                        overalllength=row["OverallLength"],
                        receiver=row["Receiver"],
                        safety=row["Safety"],
                        sights=row["Sights"],
                        stockframegrips=row["StockFrameGrips"],
                        magazine=row["Magazine"],
                        weight=row["Weight"],
                        imagename=f'https://www.lipseyscloud.com//images//{row["ImageName"]}',
                        chamber=row["Chamber"],
                        drilledandtapped=row["DrilledAndTapped"],
                        rateoftwist=row["RateOfTwist"],
                        itemtype=row["ItemType"],
                        additionalfeature1=row["AdditionalFeature1"],
                        additionalfeature2=row["AdditionalFeature2"],
                        additionalfeature3=row["AdditionalFeature3"],
                        shippingweight=row["ShippingWeight"],
                        boundbookmanufacturer=row["BoundBookManufacturer"],
                        boundbookmodel=row["BoundBookModel"],
                        boundbooktype=row["BoundBookType"],
                        exclusive=row["Exclusive"],
                        quantity=row["Quantity"],
                        allocated=row["Allocated"],
                        onsale=row["OnSale"],
                        price=row["Price"],
                        currentprice=row["CurrentPrice"],
                        retailmap=row["RetailMap"],
                        fflrequired=row["FflRequired"],
                        sotrequired=row["SotRequired"],
                        exclusivetype=row["ExclusiveType"],
                        scopecoverincluded=row["ScopeCoverIncluded"],
                        special=row["Special"],
                        sightstype=row["SightsType"],  
                        case=row["Case"],
                        family=row["Family"],
                        packagelength=row["PackageLength"],
                        packagewidth=row["PackageWidth"],
                        packageheight=row["PackageHeight"],
                        itemgroup=row["ItemGroup"],
                        features=json.dumps(features),
                    )
                )

            
            Lipsey.objects.bulk_create(
                self.insert_data,
                batch_size=500
            )
            print("Lipsey upload completed successfully.")
            return True

        except Exception as e:
            print(f"Error processing Lipsey data: {e}")
            return e

    def process_cwr(self):
        try:
            for row in self.data.iterrows():
                items = row[1].values
                items = list(items)

                features = [
                    {"Name": "Quick Specs", "Value": items[25]},
                    {"Name": "Shipping Weight", "Value": items[19]},
                    {"Name": "Box Height", "Value": items[20]},
                    {"Name": "Box Length", "Value": items[21]},
                    {"Name": "Box Width", "Value": items[22]},
                    {"Name": "Remanufactured", "Value": items[35]},
                    {"Name": "Harmonization Code", "Value": items[37]},
                    {"Name": "Country Of Origin", "Value": items[38]},
                    {"Name": "Google Merchant Category", "Value": items[48]},
                    {"Name": "Prop 65", "Value": items[53]},
                ]

                self.insert_data.append(
                    Cwr(
                        cwr_part_number=items[0],
                        manufacturer_part_number=items[1],
                        upc=items[2],
                        quantity_available_to_ship_combined=items[3],
                        quantity_available_to_ship_nj=items[4],
                        quantity_available_to_ship_fl=items[5],
                        next_shipment_date_combined=items[6],
                        next_shipment_date_nj=items[7],
                        next_shipment_date_fl=items[8],
                        your_cost=items[9],
                        list_price=items[10],
                        m_a_p_price=items[11],
                        m_r_p_price=items[12],
                        uppercase_title=items[13],
                        title=self.clean_text(items[14]),
                        full_description=items[15],
                        category_id=items[16],
                        category_name=items[17],
                        manufacturer_name=items[18],
                        shipping_weight=items[19],
                        box_height=items[20],
                        box_length=items[21],
                        box_width=items[22],
                        list_of_accessories_by_sku=items[23],
                        list_of_accessories_by_mfg=items[24],
                        quick_specs=self.clean_text(items[25]),
                        image_300x300_url=items[26],
                        image_1000x1000_url=items[27],
                        non_stock=items[28],
                        drop_ships_direct_from_vendor=items[29],
                        hazardous_materials=items[30],
                        truck_freight=items[31] in ["true", "True", True, "1", 1],
                        exportable=items[32],
                        first_class_mail=items[33],
                        oversized=items[34] in ["true", "True", True, "1", 1],
                        remanufactured=items[35],
                        closeout=items[36],
                        harmonization_code=items[37],
                        country_of_origin=items[38],
                        sale=items[39],
                        original_price_if_on_sale_closeout=items[40],
                        sale_start_date=items[41],
                        sale_end_date=items[42],
                        rebate=items[43],
                        rebate_description=items[44],
                        rebate_start_date=items[46],
                        rebate_end_date=items[47],
                        google_merchant_category=items[48],
                        quick_guide_literature_pdf_url=items[49],
                        owners_manual_pdf_url=items[50],
                        brochure_literature_pdf_url=items[51],
                        installation_guide_pdf_url=items[52],
                        video_urls=items[53],
                        prop_65=items[54],
                        prop_65_description=items[55],
                        free_shipping=items[56],
                        free_shipping_end_date=items[57],
                        returnable=items[58] in ["true", "True", True, "1", 1],
                        image_additional_1000x1000_urls=items[59],
                        case_qty_nj=items[60],
                        case_qty_fl=items[61],
                        number_3rd_party_marketplaces=items[62] in ["true", "True", True, "1", 1],
                        fcc_id=items[63],
                        sku=items[64],
                        mfgn=items[65],
                        qty=items[66],
                        qtynj=items[67],
                        qtyfl=items[68],
                        price=items[69],
                        map=items[70],
                        mrp=items[71],
                        features=json.dumps(features),
                    )
                )
            Cwr.objects.bulk_create(
                self.insert_data,
                batch_size=300,
                update_conflicts=True,
                update_fields=["qty", "qtynj", "qtyfl", "price", "map", "mrp"],
            )
            print("CWR upload completed successfully.")
            return True

        except Exception as e:
            print(f"Error processing CWR data: {e}")
            return e
        
    def process_zanders(self):
        try:
            for row in self.data.iterrows():
                items = row[1]

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
                
            Zanders.objects.bulk_create(
                    self.insert_data,
                    batch_size=500,
                    update_conflicts=True,
                    update_fields=[
                        "price1",
                        "price2",
                        "price3",
                        "qty1",
                        "qty2",
                        "qty3",
                    ],
                )
            print("Zanders upload completed successfully.")

            return True

        except Exception as e:
            print(f"An error occurred: {e}")
            return e
        
    def process_rsr(self):
        try:
            for row in self.data.iterrows():
                row = row[1]

                # Convert naive datetime to aware datetime using Django's timezone utility
                last_modified = pd.to_datetime(row["LastModified"])
                if timezone.is_naive(last_modified):
                    last_modified = timezone.make_aware(last_modified, timezone.get_current_timezone())
                

                if int(row['ImageCount']) > 0:
                    images = [f"https://img.rsrgroup.com/highres-pimages/{row['SKU']}_{count}_HR.jpg"  for count in range(int(row['ImageCount']))]
                else:
                    images = []
                try: 
                    rsr_product = Rsr( 
                        sku=row["SKU"],
                        last_modified=last_modified,
                        upc=row["UPC"],
                        title=row["Title"],
                        description=row["Description"],
                        manufacturer_code=row["ManufacturerCode"],
                        manufacturer_name=row["ManufacturerName"],
                        manufacturer_part_number=row["ManufacturerPartNumber"],
                        department_id=row["DepartmentId"],
                        department_name=row["DepartmentName"],
                        category_id=row["CategoryId"],
                        category_name=row["CategoryName"],
                        subcategory_name=row["SubcategoryName"],
                        exclusive=row["Exclusive"],
                        talo_exclusive=row["TaloExclusive"],
                        coming_soon=row["ComingSoon"],
                        new_item=row["NewItem"],
                        le_resale_only=row["LEResaleOnly"],
                        unit_of_measure=row["UnitOfMeasure"],
                        items_per_case=row["ItemsPerCase"],
                        items_per_unit=row["ItemsPerUnit"],
                        units_per_case=row["UnitsPerCase"],
                        nfa=row["NFA"],
                        hazard_warning=row["HazardWarning"],
                        image_count=row["ImageCount"],
                        msrp=row["MSRP"],
                        map=row["RetailMAP"],
                        inventory_on_hand=row["InventoryOnHand"],
                        ground_only=row["GroundOnly"],
                        drop_ship_block=row["DropShipBlock"],
                        closeout=row["Closeout"],
                        allocated=row["Allocated"],
                        drop_shippable=row["DropShippable"],
                        unit_weight=row["UnitWeight"],
                        unit_length=row["UnitLength"],
                        unit_width=row["UnitWidth"],
                        unit_height=row["UnitHeight"],
                        case_weight=row["CaseWeight"],
                        case_length=row["CaseLength"],
                        case_width=row["CaseWidth"],
                        case_height=row["CaseHeight"],
                        blemished=row["Blemished"],
                        dealer_price=row["DealerPrice"],
                        dealer_case_price=row["DealerCasePrice"],
                        features = getRsrItemAttribute(row["UPC"]),
                        images = images
                    )
                    
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return False

                # Save the product to the database
                rsr_product.save()

                # Introduce a small delay between each save (e.g., 0.5 seconds)
                time.sleep(0.5)

            print('RSR products uploaded successfully')
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return e