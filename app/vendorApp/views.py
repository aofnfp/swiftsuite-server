from django.shortcuts import render
from ftplib import FTP
import time, os, re, io
import ftplib
import ssl
import csv, json
import pandas as pd
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from .models import Fragrancex, Lipsey, Ssi, Cwr, Zanders, VendoEnronment
from django.http import JsonResponse
from django.forms.models import model_to_dict
import ast
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
import threading
from django.core.cache import cache
import uuid
from .update import periodic_task
from .apiSupplier import *
from django.db import transaction
from .pagination import CataloguePagination



class VendorActivity:
    def __init__(self):
        self.data = pd.DataFrame()
        self.insert_data = []
        self.update_catalog = False

    def clear_cache(self):
        """
        Clears the data and insert_data to reset the cache, ensuring no lingering data.
        """
        self.data = pd.DataFrame()   # Reset data
        self.insert_data.clear()     # Clear insert_data list
        print("Cache cleared.")

    def clean_text(self,text):
        # Replace specific problematic characters with more common ASCII equivalents
        replacements = {
            "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
            "\u00A0": " ",  # Non-breaking space
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        # Remove any remaining non-ASCII characters
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def main(self, suppliers, userid, get_filters = False):
        if suppliers[0] in ['Fragrancex', 'RSR']:
            value = self.process_supplier(suppliers, userid, get_filters)

        else:
            for supplier in suppliers:
                value = self.process_supplier(supplier, userid, get_filters)
                
            
        return value

    def process_supplier(self, supplier, userid, get_filters):
        """Process each supplier."""
   
        supplier_name, *_ = supplier

        print(f"Processing {supplier_name}...")
        local_dir = os.path.join("local_dir", supplier_name)
        os.makedirs(local_dir, exist_ok=True)
        try:
            value = self.download_csv_from_ftp(userid, supplier, get_filters, local_dir)
            print(f"{supplier_name} data processed successfully.")
            return value
        except Exception as e:
            print(f"Error processing {supplier_name}: {str(e)}")


    def download_csv_from_ftp(self, userid, supplier, get_filters, local_dir=".", port=21):
        """Download CSV file from FTP server."""
        
        if supplier[0] == 'Fragrancex':
            supplier_name, apiAccessId, apiAccessKey = supplier
            data = getFragranceXData(apiAccessId, apiAccessKey)
            file_name = "frangrancex.csv"
            file_path = os.path.join(local_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                # Create a writer object
                if 'RetailPriceUSD' not in data[3].keys():
                    data[3]['RetailPriceUSD'] = 0
                writer = csv.DictWriter(file, fieldnames=data[3].keys())
                writer.writeheader()
                # Write the data
                writer.writerows(data)

            print(f"Data successfully written to {file_path}")
            value = self.process_csv(userid,supplier_name, local_dir, file_name, get_filters)
            return value

        elif supplier[0] == 'RSR':
            supplier_name, Username, Password, POS = supplier
            data = getRSR(Username, Password, POS)
            file_name = "rsr.csv"
            file_path = os.path.join(local_dir, file_name)
            with open(file_path, mode='w', newline='', encoding = 'utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

            print(f"Data successfully written to {file_path}")
            value = self.process_csv(userid, supplier_name, local_dir, file_name, get_filters)
            return value

        else:
            supplier_name, ftp_host, ftp_user, ftp_password, ftp_path, file_name, index, port = supplier
            file_path = os.path.join(local_dir, file_name)
            
            ftp = FTP()
            ftp.connect(ftp_host, port)
            ftp.login(user=ftp_user, passwd=ftp_password)
            ftp.set_pasv(True)
            ftp.cwd(ftp_path)
            with open(os.path.join(local_dir, file_name), "wb") as local_file:
                ftp.retrbinary(f"RETR {file_name}", local_file.write)
        
            print(f"{file_name} downloaded from FTP for {ftp_user}.")

            value = self.process_csv(userid,supplier_name, local_dir, file_name, get_filters, index)
            return value

    def process_csv(self, userid, supplier_name, local_dir, file_name, get_filters, index =  1 ):
        with open(os.path.join(local_dir, file_name), "r", encoding='latin1') as file:
            csv_data = csv.DictReader(file)
            print(csv_data, supplier_name)

            supplier_name = supplier_name.upper()

            if supplier_name == "FRAGRANCEX":
                if get_filters:
                    filter_values = self.filters_fragranceX(userid, csv_data)
                    return filter_values
                else:
                    success = self.process_fragranceX(userid, csv_data)
                    return success
            elif supplier_name == "LIPSEY":
                if get_filters:
                    filter_values = self.filters_lipsey(userid, csv_data)
                    return filter_values
                else:
                    success = self.process_lipsey(userid, csv_data)
                    return success
            elif supplier_name == "SSI":
                if get_filters:
                    filter_values = self.filters_ssi(userid, csv_data)
                    return filter_values
                else:
                    success = self.process_ssi(userid, csv_data)
                    return success
            elif supplier_name == "CWR":
                if get_filters:
                    filter_values = self.filters_cwr(userid, csv_data, index)
                    return filter_values
                else:
                    success = self.process_cwr(userid, csv_data, index)
                    return success
            elif supplier_name == "RSR":
                if get_filters:
                    filter_values = self.filters_rsr(userid, csv_data)
                    return filter_values
                else:
                    success =self.process_rsr(userid, csv_data)
                    return success
            elif supplier_name == "ZANDERS":
                if get_filters:
                    filter_values = self.filters_zanders(userid, csv_data, index)
                    return filter_values
                else:
                    success = self.process_zanders(userid, csv_data, index)
                    return success
        
    def filters_fragranceX(self, userid, csv_data):
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
    
    def filters_lipsey(self, userid, csv_data):
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

    def filters_ssi(self, userid, csv_data):
        items = []
        for row in csv_data:
            header = str(row).split(":", 1)[0]
            header = header.replace("{'", "").split("|")
            item = re.sub("[\"\'}\' ']", "", str(row))
            item = item.split(":", 1)[1]
            item = item.replace("]}", "").split("|")
            item[-1] = item[-1].replace("]", "")
            items.append(item)
            
        header[-1] = header[-1].replace("'", "")
        
        self.data = pd.DataFrame(items, columns=header)
        category = self.data['Category'].unique()

        category_dictList = []
        x = 1
        for value in category:
            _dict = {"id":x, "label":value, "checked":False}
            category_dictList.append(_dict)
            x+=1
        filter_values = {'category':category_dictList}
        return filter_values
    
    def filters_cwr(self, userid, csv_data, index):
        items = []
        for row in csv_data:
            items.append(row)
            
        if index == 1:
            self.data = pd.DataFrame(items)
        elif index == 2:
            data2 = pd.DataFrame(items)
            self.data = self.data.merge(data2, left_on="CWR Part Number", right_on="sku")  
        
        return {}

    def filters_rsr(self, userid, csv_data):
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
    
    def filters_zanders(self, userid, csv_data, index):
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

        elif index == 2:
            data2 = pd.DataFrame(items)
            self.data = self.data.merge(data2, left_on="ItemNumber", right_on="itemnumber")

        else:
            self.data = pd.DataFrame(items)

        manufacturer = self.data['manufacturer'].unique()
        manufacturer_dictList = []
        for x, value in enumerate(manufacturer, start=1):
            manufacturer_dictList.append({"id": x, "label": value, "checked": False})
        filter_values = {'manufacturer': manufacturer_dictList}

        return filter_values

    def process_fragranceX(self, userid):
        
        products = Fragrancex.objects.filter(user_id = userid)
        if products.exists() and not self.update_catalog:
            print('Fragrancex products already uploaded for this user.')
            return True
        
        try:
            for _, row in self.data.iterrows():
            
                description = self.clean_text(row.get("Description", ""))
                productName = row.get("ProductName", "")
                itemId = row.get("ItemId", "")
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
                self.insert_data.append(Fragrancex(user_id=userid, productName=productName, itemId=itemId, description=description, brandName=brandName, gender=gender, size=size, metric_size=metric_size, retailPriceUSD=retailPriceUSD, wholesalePriceUSD=wholesalePriceUSD, wholesalePriceEUR=wholesalePriceEUR,wholesalePriceGBP=wholesalePriceGBP, wholesalePriceCAD=wholesalePriceCAD, wholesalePriceAUD=wholesalePriceAUD, smallImageUrl=smallImageUrl,largeImageUrl=largeImageUrl, type=productType, quantityAvailable=quantityAvailable,upc=upc, instock=instock, parentCode=parentCode, features = json.dumps(features), total_product_cost = compute_price(wholesalePriceUSD) ))
                
            if not self.update_catalog:
                # Insert data into database
                Fragrancex.objects.bulk_create(self.insert_data, batch_size=500, update_conflicts=True, update_fields=["size", "retailPriceUSD", "wholesalePriceUSD", "wholesalePriceEUR", "wholesalePriceGBP", "wholesalePriceCAD", "wholesalePriceAUD", "quantityAvailable",  "features", "total_product_cost"])
                print('FrangranceX upload successfully')
                return True
            else:
                # write the functionality to bulk update fragrancex
                existing_data = Fragrancex.objects.filter(
                    itemId__in=[item.itemId for item in self.insert_data]
                )
                existing_data_dict = {item.itemId: item for item in existing_data}

                # Update fields for existing records or add new ones
                for item in self.insert_data:
                    if item.itemId in existing_data_dict:
                        existing_record = existing_data_dict[item.itemId]
                        # Update only the specified fields
                        existing_record.productName = item.productName
                        existing_record.size = item.size
                        existing_record.retailPriceUSD = item.retailPriceUSD
                        existing_record.wholesalePriceUSD = item.wholesalePriceUSD
                        existing_record.wholesalePriceEUR = item.wholesalePriceEUR
                        existing_record.wholesalePriceGBP = item.wholesalePriceGBP
                        existing_record.wholesalePriceCAD = item.wholesalePriceCAD
                        existing_record.wholesalePriceAUD = item.wholesalePriceAUD
                        existing_record.quantityAvailable = item.quantityAvailable
                        existing_record.features = item.features
                        existing_record.total_product_cost = item.total_product_cost
                    else:
                        # If not found, add it as a new record
                        existing_data_dict[item.itemId] = item

                # Perform the bulk update
                Fragrancex.objects.bulk_update(
                    existing_data_dict.values(),
                    fields=[
                        "productName",
                        "size",
                        "retailPriceUSD",
                        "wholesalePriceUSD",
                        "wholesalePriceEUR",
                        "wholesalePriceGBP",
                        "wholesalePriceCAD",
                        "wholesalePriceAUD",
                        "quantityAvailable",
                        "features",
                        "total_product_cost",
                    ],
                )

            print("FragranceX update completed successfully")
            return True

        except Exception as e:
            return e
    
    def process_lipsey(self, userid):
        products = Lipsey.objects.filter(user_id=userid)
        if products.exists() and not self.update_catalog:
            print("Lipsey products already uploaded for this user.")
            return True

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
                        user_id=userid,
                        itemnumber=row["ItemNo"],
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
                        imagename= f'https://www.lipseyscloud.com//images//{row["ImageName"]}',
                        chamber=row["Chamber"],
                        drilledandtapped=row["DrilledAndTapped"],
                        rateoftwist=row["RateOfTwist"],
                        itemtype=row["ItemType"],
                        additionalfeature1=row["AdditionalFeature1"],
                        additionalfeature2=row["AdditionalFeature2"],
                        additionalfeature3=row["AdditionalFeature3"],
                        shippingweight=row["ShippingWeight"],
                        features=json.dumps(features),
                        total_product_cost=compute_price(row["Price"]),
                    )
                )

            # Handle updates if self.update_catalog is True
            if self.update_catalog:
                existing_items = Lipsey.objects.filter(
                    itemnumber__in=[item.itemnumber for item in self.insert_data]
                )
                existing_items_dict = {item.itemnumber: item for item in existing_items}

                for item in self.insert_data:
                    if item.itemnumber in existing_items_dict:
                        existing_record = existing_items_dict[item.itemnumber]
                        # Update specified fields
                        existing_record.price = item.price
                        existing_record.currentprice = item.currentprice
                        existing_record.onsale = item.onsale
                        existing_record.features = item.features
                        existing_record.total_product_cost = item.total_product_cost
                    else:
                        # Add as new record
                        existing_items_dict[item.itemnumber] = item

                Lipsey.objects.bulk_update(
                    existing_items_dict.values(),
                    fields=["price", "currentprice", "onsale", "features", "total_product_cost"],
                )
                print("Lipsey records updated successfully.")
            else:
                Lipsey.objects.bulk_create(
                    self.insert_data,
                    batch_size=500,
                    update_conflicts=True,
                    update_fields=["onsale", "price", "currentprice"],
                )
                print("Lipsey upload completed successfully.")
            return True

        except Exception as e:
            print(f"Error processing Lipsey data: {e}")
            return e

    def process_ssi(self, userid):
        products = Ssi.objects.filter(user_id=userid)
        if products.exists() and not self.update_catalog:
            print("SSI products already uploaded for this user.")
            return True

        try:
            for row in self.data.iterrows():
                items = row[1].values

                features = [
                    {"Name": "DimensionH", "Value": items[3]},
                    {"Name": "DimensionL", "Value": items[4]},
                    {"Name": "DimensionW", "Value": items[5]},
                    {"Name": "Manufacturer", "Value": items[6]},
                    {"Name": "UPC Code", "Value": items[9]},
                    {"Name": "Weight", "Value": items[10]},
                    {"Name": "Weight Units", "Value": items[11]},
                    {"Name": "Category", "Value": items[12]},
                    {"Name": "Subcategory", "Value": items[13]},
                    {"Name": "Shipping Weight", "Value": items[20]},
                    {"Name": "Shipping Length", "Value": items[21]},
                    {"Name": "Shipping Width", "Value": items[22]},
                    {"Name": "Shipping Height", "Value": items[23]},
                    {"Name": "Attribute 1", "Value": items[24]},
                    {"Name": "Attribute 2", "Value": items[25]},
                    {"Name": "Attribute 3", "Value": items[26]},
                    {"Name": "Attribute 4", "Value": items[27]},
                    {"Name": "Attribute 5", "Value": items[28]},
                    {"Name": "Attribute 6", "Value": items[29]},
                    {"Name": "Attribute 7", "Value": items[30]},
                    {"Name": "Prop 65 Warning", "Value": items[31]},
                    {"Name": "Prop 65 Reason", "Value": items[32]},
                    {"Name": "Country of Origin", "Value": items[33]},
                ]
                

                self.insert_data.append(
                    Ssi(
                        user_id=userid,
                        sku=items[0],
                        description=items[1],
                        datecreated=items[2],
                        dimensionh=items[3],
                        dimensionl=items[4],
                        dimensionw=items[5],
                        manufacturer=items[6],
                        imageurl=items[7],
                        thumbnailurl=items[8],
                        upccode=items[9],
                        weight=items[10],
                        weightunits=items[11],
                        category=items[12],
                        subcategory=items[13],
                        status=items[14],
                        map=items[15],
                        msrp=items[16],
                        mpn=items[17],
                        minimumorderquantity=items[18],
                        detaileddescription=items[19],
                        shippingweight=items[20],
                        shippinglength=items[21],
                        shippingwidth=items[22],
                        shippingheight=items[23],
                        attribute1=items[24],
                        attribute2=items[25],
                        attribute3=items[26],
                        attribute4=items[27],
                        attribute5=items[28],
                        attribute6=items[29],
                        attribute7=items[30],
                        prop65warning=items[31],
                        prop65reason=items[32],
                        countryoforigin=items[33],
                        groundshippingrequired=items[34],
                        features=json.dumps(features),
                    )
                )

            # Handle updates if self.update_catalog is True
            if self.update_catalog:
                existing_items = Ssi.objects.filter(
                    sku__in=[item.sku for item in self.insert_data]
                )
                existing_items_dict = {item.sku: item for item in existing_items}

                for item in self.insert_data:
                    if item.sku in existing_items_dict:
                        existing_record = existing_items_dict[item.sku]
                        # Update specified fields
                        existing_record.description = item.description
                        existing_record.status = item.status
                        existing_record.weight = item.weight
                        existing_record.features = item.features
                    else:
                        # Add as new record
                        existing_items_dict[item.sku] = item

                Ssi.objects.bulk_update(
                    existing_items_dict.values(),
                    fields=["description", "status", "weight", "features"],
                )
                print("SSI records updated successfully.")
            else:
                Ssi.objects.bulk_create(
                    self.insert_data,
                    batch_size=500,
                    update_conflicts=True,
                    update_fields=["description", "status", "weight"],
                )
                print("SSI upload completed successfully.")
            return True

        except Exception as e:
            print(f"Error processing SSI data: {e}")
            return e


    def process_cwr(self, userid):
        products = Cwr.objects.filter(user_id=userid)
        if products.exists() and not self.update_catalog:
            print("CWR products already uploaded for this user.")
            return True

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
                        user_id=userid,
                        cwr_part_number=items[0],
                        manufacturer_part_number=items[1],
                        upc_code=items[2],
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
                        total_product_cost=compute_price(items[69]),
                    )
                )

            # Handle updates if self.update_catalog is True
            if self.update_catalog:
                existing_items = Cwr.objects.filter(
                    sku__in=[item.sku for item in self.insert_data]
                )
                existing_items_dict = {item.sku: item for item in existing_items}

                for item in self.insert_data:
                    if item.sku in existing_items_dict:
                        existing_record = existing_items_dict[item.sku]
                        # Update specified fields
                        existing_record.qty = item.qty
                        existing_record.qtynj = item.qtynj
                        existing_record.qtyfl = item.qtyfl
                        existing_record.price = item.price
                        existing_record.map = item.map
                        existing_record.mrp = item.mrp
                        existing_record.features = item.features
                        existing_record.total_product_cost = item.total_product_cost
                    else:
                        # Add as new record
                        existing_items_dict[item.sku] = item

                Cwr.objects.bulk_update(
                    existing_items_dict.values(),
                    fields=["qty", "qtynj", "qtyfl", "price", "map", "mrp"],
                )
                print("CWR records updated successfully.")
            else:
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

    
    def process_rsr(self, userid):
        products = Rsr.objects.filter(user_id=userid)
        if products.exists():
            print('RSR products already uploaded for this user.')
            return True
        else:
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
                    
                    rsr_product = Rsr(
                        user_id=userid,
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
                        retail_map=row["RetailMAP"],
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
                        total_product_cost = compute_price(row["DealerPrice"]),
                        images = json.dumps(images)
                    )

                    # Save the product to the database
                    rsr_product.save()

                    # Introduce a small delay between each save (e.g., 0.5 seconds)
                    time.sleep(0.5)

                print('RSR products uploaded successfully')
                return True
            except Exception as e:
                print(f"An error occurred: {e}")
                return e
 
    def process_zanders(self, userid):
        products = Zanders.objects.filter(user_id=userid)
        if products.exists() and not self.update_catalog:
            print("Zanders products already uploaded for this user.")
            return True

        try:
            for row in self.data.iterrows():
                items = row[1]

                features = [
                    {"name": "Weight", "value": items['weight']},
                ]
                
                zanders_product = Zanders(
                    user_id=userid,
                    available=items['available'],
                    category=items['category'],
                    desc1=items['desc1'],
                    desc2=items['desc2'],
                    itemnumber=items['itemnumber'],
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
                    mapprice=items['mapprice'],
                    imagelink=items['ImageLink'],
                    description=items["description"],
                    features=json.dumps(features),
                    total_product_cost=compute_price(items["price1"]),
                )

                # Add to the batch for bulk processing
                self.insert_data.append(zanders_product)

            # Handle updates or inserts based on `self.update_catalog`
            if self.update_catalog:
                existing_items = Zanders.objects.filter(
                    itemnumber__in=[item.itemnumber for item in self.insert_data]
                )
                existing_items_dict = {item.itemnumber: item for item in existing_items}

                for item in self.insert_data:
                    if item.itemnumber in existing_items_dict:
                        existing_record = existing_items_dict[item.itemnumber]
                        # Update specified fields
                        existing_record.price1 = item.price1
                        existing_record.price2 = item.price2
                        existing_record.price3 = item.price3
                        existing_record.qty1 = item.qty1
                        existing_record.qty2 = item.qty2
                        existing_record.qty3 = item.qty3
                        existing_record.msrp = item.msrp
                        existing_record.mapprice = item.mapprice
                        existing_record.features = item.features
                        existing_record.total_product_cost = item.total_product_cost
                    else:
                        # Add as new record
                        existing_items_dict[item.itemnumber] = item

                Zanders.objects.bulk_update(
                    existing_items_dict.values(),
                    fields=[
                        "price1",
                        "price2",
                        "price3",
                        "qty1",
                        "qty2",
                        "qty3",
                        "msrp",
                        "mapprice",
                        "features",
                        "total_product_cost",
                    ],
                )
                print("Zanders records updated successfully.")
            else:
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

                       

VENDORS = {
    "fragrancex":[
        ('Fragrancex', "ftp2.fragrancex.com", "frgx_temilolaoduola@gmail.com", "ftos3tpi", "/", "outgoingfeed_upc.csv", 1, 2222),
    ],

    "zanders":[
        ("Zanders", "ftp2.gzanders.com", "DotfakGroup", "Katy801", "/Inventory", "itemimagelinks.csv", 1, 21),
        ("Zanders", "ftp2.gzanders.com", "DotfakGroup", "Katy801", "/Inventory", "zandersinv.csv", 2, 21),
        ("Zanders", "ftp2.gzanders.com", "DotfakGroup", "Katy801", "/Inventory", "detaildesctext.csv", 3, 21),
    ],

    "lipsey":[
        ("Lipsey","ftp.lipseysdistribution.net", "cat800459", "8b4c531467417ad97e5274d5ecfbc0eb", "/", "catalog.csv", 1, 21),
    ],

    "ssi":[
        ("SSI","www.rapidretail.net", "ssi_dot774rr", "Rapid_774!", "/Products", "RR_Products.csv", 1, 21),
    ],

    "cwr":[
        ("CWR", "edi.cwrdistribution.com", "421460", "QUwB6I1m", "/out", "catalog.csv", 1, 21),
        ("CWR", "edi.cwrdistribution.com", "421460", "QUwB6I1m",  "/out", "inventory.csv", 2, 21)
    ],

    "rsr":[
        ("RSR", "ftps.rsrgroup.com", "49554", "aFsBCwSF", "/keydealer", "rsrinventory-keydlr-new.txt", 1, 2222),
        ("RSR", "ftps.rsrgroup.com", "49554", "aFsBCwSF", "/keydealer", "product_sell_descriptions.txt", 2, 2222),
        ("RSR", "ftps.rsrgroup.com", "49554", "aFsBCwSF", "/keydealer", "IM-QTY-CSV.csv", 3, 2222),
        ("RSR", "ftps.rsrgroup.com", "49554", "aFsBCwSF", "/keydealer", "rsr-product-message.txt", 4, 2222),
    ]

}


MODELS_MAPPING = {
        'fragrancex': Fragrancex,
        'cwr': Cwr,
        'lipsey': Lipsey,
        'ssi': Ssi,
        'zanders': Zanders,
        'rsr': Rsr
    }


fixedVendorMarkup = 0
percentageVendorMarkup = 0
shipping_cost = 0
def compute_price(productCost):
    if productCost:
        productCost = float(productCost)
        totalProductCost = productCost + float(fixedVendorMarkup) + ((float(percentageVendorMarkup)/100) * productCost) + float(shipping_cost)
        totalProductCost = round(totalProductCost, 2)
        return str(totalProductCost)
    else:
        return "0"



def get_suppliers_for_vendor(ftp_name, ftp_host, ftp_user, ftp_password):
    if ftp_name == 'Zanders':
        return [
            (ftp_name, ftp_host, ftp_user, ftp_password, "/Inventory", "itemimagelinks.csv", 1, 21),
            (ftp_name, ftp_host, ftp_user, ftp_password, "/Inventory", "zandersinv.csv", 2, 21),
            (ftp_name, ftp_host, ftp_user, ftp_password, "/Inventory", "detaildesctext.csv", 3, 21),
        ]
    elif ftp_name == 'CWR':
        return [
            (ftp_name, ftp_host, ftp_user, ftp_password, "/out", "catalog.csv", 1, 21),
            (ftp_name, ftp_host, ftp_user, ftp_password, "/out", "inventory.csv", 2, 21)
        ]
    elif ftp_name == 'Lipsey':
        return [(ftp_name, ftp_host, ftp_user, ftp_password, "/", "catalog.csv", 1, 21)]
    elif ftp_name == 'SSI':
        return [(ftp_name, ftp_host, ftp_user, ftp_password, "/Products", "RR_Products.csv", 1, 21)]


class VendorEnrolmentTestView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = VendorEnrolmentTestSerializer(data=request.data)
        serializer.is_valid()
        vendor = serializer.data
        userid = request.user.id
        ftp_name = vendor['vendor_name']
        pull = VendorActivity()


        if ftp_name == "Fragrancex":
            apiAccessId = vendor['apiAccessId']
            apiAccessKey = vendor['apiAccessKey']
            supplier = (ftp_name, apiAccessId, apiAccessKey)
            filter_values = pull.main(supplier, userid, get_filters=True)

        elif ftp_name == 'RSR':
            Username = vendor['Username']
            Password = vendor['Password']
            POS = vendor['POS']
            supplier = (ftp_name, Username, Password, POS)
            filter_values = pull.main(supplier, userid, get_filters=True)

        else:
                    
            ftp_host = vendor['host']
            ftp_user = vendor['ftp_username']
            ftp_password = vendor['ftp_password']
            suppliers = get_suppliers_for_vendor(ftp_name, ftp_host, ftp_user, ftp_password)
            # print(suppliers)            
            filter_values = pull.main(suppliers, userid, get_filters=True)

        if filter_values or filter_values == {}:
            cache_key = f'vendor_data_{request.user.id}'
            cache.set(cache_key, pull.data.to_json(orient='records'), timeout=3600)

            return Response(filter_values, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

class VendoEnronmentView(APIView):
    permission_classes = [IsAuthenticated]
    
    
    def get(self, request):
        vendor_enronments = VendoEnronment.objects.filter(user_id=request.user.id)
        serializer = VendoEnronmentSerializer(vendor_enronments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = VendoEnronmentSerializer(data=request.data, context={'request': request})
        self.pull = VendorActivity()

        # Retrieve data from cache
        cache_key = f'vendor_data_{request.user.id}'
        vendor_data_json = cache.get(cache_key)
        if vendor_data_json:
            self.pull.data = pd.read_json(io.StringIO(vendor_data_json))
        

        if serializer.is_valid():
            self.vendor_data = serializer.validated_data
            self.userid = request.user.id
            self.ftp_name = self.vendor_data['vendor_name']
                    
            # pricing value 
            global fixedVendorMarkup, percentageVendorMarkup, shipping_cost
            fixedVendorMarkup = self.vendor_data.get('fixed_markup', 0)
            percentageVendorMarkup = self.vendor_data.get('percentage_markup', 0)
            shipping_cost = self.vendor_data.get('shipping_cost', 0)
            
            # Generate a unique task ID
            task_id = str(uuid.uuid4())

            if self.ftp_name.upper() == 'RSR':
                # Run process_rsr in a separate thread
                thread = threading.Thread(target=self.process_rsr_in_background, args=(serializer, task_id))
                thread.start()

                # Return a response immediately
                return Response({"task_id": task_id, "message": "RSR processing started in the background"}, status=status.HTTP_202_ACCEPTED)

            # Handle other vendors synchronously (non-threaded)
            success = self.process_vendor(self.userid)
            
            if success:
                serializer.save()
                self.pull.clear_cache()
                # Start periodic update in a background thread
                self.start_periodic_update()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": str(success)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def process_vendor(self, userid):
        if self.ftp_name.upper() == 'FRAGRANCEX':
            return self.pull.process_fragranceX(userid)
        elif self.ftp_name.upper() == 'CWR':
            return self.pull.process_cwr(userid)
        elif self.ftp_name.upper() == 'LIPSEY':                    
            return self.pull.process_lipsey(userid)
        elif self.ftp_name.upper() == 'SSI':
            return self.pull.process_ssi(userid)
        elif self.ftp_name.upper() == 'ZANDERS':
            return self.pull.process_zanders(userid)
        return False

    def process_rsr_in_background(self, serializer, task_id):
        try:
            # Step 1: Starting the task, setting progress to 10%
            cache.set(f"upload_progress_{task_id}", 10)
            time.sleep(2)

            # Step 2: Process RSR data
            success = self.pull.process_rsr(self.userid)  # Ensure this returns True/False

            if success:
                # Save serializer data on successful processing
                serializer.save()
                cache.set(f"upload_progress_{task_id}", 100)  # Mark completion
                self.start_periodic_update()
            else:
                cache.set(f"upload_progress_{task_id}", -1)  # Mark as failed
        except Exception as e:
            # Detailed exception handling
            cache.set(f"upload_progress_{task_id}", -1)
            print(f"Error processing RSR in background: {str(e)}")

    def start_periodic_update(self):
        # Extract relevant data for the periodic task
        ftp_name = self.vendor_data['vendor_name']
        ftp_host = self.vendor_data.get('host')
        ftp_user = self.vendor_data.get('ftp_username')
        ftp_password = self.vendor_data.get('ftp_password')
        apiAccessId = self.vendor_data.get('apiAccessId')
        apiAccessKey = self.vendor_data.get('apiAccessKey')
        username = self.vendor_data.get('Username')
        password = self.vendor_data.get('Password')
        pos = self.vendor_data.get('POS')

        # Run the periodic task in a new thread
        thread = threading.Thread(
            target=periodic_task,
            args=(
                ftp_name,
                self.userid,
                ftp_host,
                ftp_user,
                ftp_password,
                apiAccessId,
                apiAccessKey,
                username,
                password,
                pos
            ),
            daemon=True
        )
        thread.start()

class UploadProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        # Get the progress from the cache
        progress = cache.get(f"upload_progress_{task_id}")

        if progress is not None:
            return Response({"task_id": task_id, "progress": progress}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Task ID not found"}, status=status.HTTP_404_NOT_FOUND)



@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_vendor_enrolment(request, identifier):
    enrolment_list = get_object_or_404(VendoEnronment, user_id=request.user.id, vendor_identifier=identifier)
    serializer = VendoEnronmentSerializer(enrolment_list, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vendor_enrolment(request, identifier):
    enrolment = get_object_or_404(VendoEnronment, user_id=request.user.id, vendor_identifier=identifier)
    enrolment.delete()
    
    return Response({"message":"Enrollment Deleted Successfully"}, status=status.HTTP_200_OK)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vendorData(request, vendor_name):
    vendor_name = vendor_name.lower()

    # Validate vendor_name
    if vendor_name not in MODELS_MAPPING.keys():
        return Response(
            {"error": f"Vendor '{vendor_name}' is not recognized."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            # Delete all vendor enrolment first
            VendoEnronment.objects.filter(user_id=request.user.id, vendor_name=vendor_name).delete()
            
            # Delete vendor-specific data
            
            MODELS_MAPPING[vendor_name].objects.filter(user_id=request.user.id).delete()
        
        return Response(
            {"message": "Vendor data and enrollments deleted successfully."}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        
        return Response(
            {"error": "An error occurred while deleting vendor data.", "details": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getEnrolmentWithIdentifier(request, identifier):
    enrolment = get_object_or_404(VendoEnronment, vendor_identifier = identifier)
    serializer = VendoEnronmentSerializer(enrolment)
    
    vendor_name = enrolment.vendor_name.lower()
    vendor_model = MODELS_MAPPING.get(vendor_name)
    vendor_data = vendor_model.objects.filter(user_id=request.user.id)
    
    # Process data based on vendor name
    response_data = {'enrolment': serializer.data}
    if vendor_name == 'rsr':
        product_category = (
            vendor_data.values_list('category_name', flat=True)
            .distinct()
        )
        manufacturer = (
            vendor_data.values_list('manufacturer_name', flat=True)
            .distinct()
        )
        shippable = (
            vendor_data.values_list('drop_shippable', flat=True)
            .distinct()
        )
        
        response_data['product_category'] = list(product_category)
        response_data['manufacturer'] = list(manufacturer)
        response_data['shippable'] = list(shippable)
        
    elif vendor_name == 'fragrancex':
        brand = (
            vendor_data.values_list('brandName', flat=True)
            .distinct()
        )
        response_data['brand'] = list(brand)
        
    elif vendor_name == 'lipsey':
        product_filter = (
            vendor_data.values_list('itemtype', flat=True)
            .distinct()
        )
        
        manufacturer = (
            vendor_data.values_list('manufacturer', flat=True)
            .distinct()
        )
        
        response_data['product_filter'] = list(product_filter)
        response_data['manufacturer'] = list(manufacturer)
        
    elif vendor_name == 'zanders':
        manufacturer = (
            vendor_data.values_list('manufacturer', flat=True)
            .distinct()
        )
        response_data['manufacturer'] = list(manufacturer)
    
    elif vendor_name == 'ssi':
        product_category = (
            vendor_data.values_list('category', flat=True)
            .distinct()
        )
        
        response_data['product_category'] = list(product_category)
    # Return the response
    return JsonResponse(response_data, status=status.HTTP_200_OK)
    
    
    
class CatalogueBaseView(ListAPIView):
    permission_classes = [IsAuthenticated]
    model = None  # Subclasses must override this
    vendor_name = ''
    pagination_class = CataloguePagination 

    def get_queryset(self):
        userid = self.request.user.id
        identifier = self.kwargs.get('identifier', None)
        
        if identifier:
            try:
                vendor_data = VendoEnronment.objects.get(
                    user_id=userid, 
                    vendor_name=self.vendor_name, 
                    vendor_identifier=identifier
                )
            except VendoEnronment.DoesNotExist:
                return self.model.objects.none()
            
            filters = {'user_id': userid, 'active': False}
            
            if self.vendor_name == 'Lipsey':
                filters.update({
                    'itemtype__in': vendor_data.product_filter or [],
                    'manufacturer__in': vendor_data.manufacturer or [],
                })
            elif self.vendor_name == 'FragranceX':
                filters.update({'brandName__in': vendor_data.brand or []})
            elif self.vendor_name == 'RSR':
                filters.update({
                    'category_name__in': vendor_data.product_category or [],
                    'manufacturer_name__in': vendor_data.manufacturer or [],
                    'drop_shippable__in': vendor_data.shippable or [],
                })
            elif self.vendor_name == 'CWR':
                filters.update({
                    'returnable': vendor_data.returnable,
                    'number_3rd_party_marketplaces': vendor_data.third_party_marketplaces,
                    'oversized': vendor_data.oversized,
                    'truck_freight': vendor_data.truck_freight,
                })
            elif self.vendor_name == 'SSI':
                filters.update({'category__in': vendor_data.product_category or []})
            elif self.vendor_name == 'Zanders':
                filters.update({
                    'serialized': 'Yes' if vendor_data.serialized else 'No',
                    'manufacturer__in': vendor_data.manufacturer or [],
                })

            return self.model.objects.filter(**filters)

        return self.model.objects.filter(user_id=userid)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().values()  
        
        if not queryset:
            return Response({"message": "No data found"}, status=status.HTTP_404_NOT_FOUND)

        # Extract vendor identifiers
        vendor = VendoEnronment.objects.filter(user_id=self.kwargs.get("pk"))
        serializer = VendoEnronmentSerializer(vendor, many=True)

        all_identifiers = [
            {"id": index + 1, "vendor_identifier": item["vendor_identifier"]}
            for index, item in enumerate(serializer.data)
        ]

        # Paginate queryset
        page = self.paginate_queryset(queryset) 
        if page is not None:
            paginated_response = self.get_paginated_response(page).data 
            paginated_response["all_identifiers"] = all_identifiers 
            return Response(paginated_response)

        # Fallback if pagination is disabled
        return Response({"results": queryset, "all_identifiers": all_identifiers})
    
class CatalogueFragrancexView(CatalogueBaseView):
    model = Fragrancex
    vendor_name = 'FragranceX'
class CatalogueZandersView(CatalogueBaseView):
    model = Zanders
    vendor_name = 'Zanders'
class CatalogueLipseyView(CatalogueBaseView):
    model = Lipsey
    vendor_name = 'Lipsey'
class CatalogueSsiView(CatalogueBaseView):
    model = Ssi
    vendor_name = 'SSI'
class CatalogueCwrView(CatalogueBaseView):
    model = Cwr
    vendor_name = 'CWR'
class CatalogueRsrView(CatalogueBaseView):
    model = Rsr
    vendor_name = 'RSR'

class AllCatalogueView(ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CataloguePagination
    
    def get_queryset(self):
        user_id = self.request.user.id
        vendors = VendoEnronment.objects.filter(user_id=user_id).values_list('vendor_name', flat=True)
        vendors = {vendor.lower() for vendor in vendors}

        if not vendors:
            return []  # Return empty list if no vendors found

        all_products = []
        for model_name, model_class in MODELS_MAPPING.items():
            if model_name in vendors:
                products = model_class.objects.filter(active=False, user_id=user_id).values()
                all_products.extend(list(products))

        return all_products  # Returning as a list of dicts

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        if not queryset:
            return Response({"message": "No data found"}, status=status.HTTP_404_NOT_FOUND)

        # Paginate the queryset (which is now a list)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(page)

        # Fallback if pagination is disabled
        return Response({"results": queryset})


class AddProductView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, userid, product_id, vendor_name, vendor_identifier = None):
        vendor_name = vendor_name.lower()

        if vendor_name not in MODELS_MAPPING:
            return JsonResponse({'error': 'Invalid vendor name'}, status=400)

        VENDOR = MODELS_MAPPING[vendor_name]

        product = get_object_or_404(VENDOR, id=product_id, user_id=userid)
        product_data = model_to_dict(product)
        
        general_product_data = self.map_vendor_data_to_general(vendor_name, product_data, userid)

        return JsonResponse(general_product_data, safe=False, status=status.HTTP_200_OK)

    def put(self, request, userid, product_id, vendor_name, vendor_identifier):
        vendor_name = vendor_name.lower()

        if vendor_name not in MODELS_MAPPING:
            return JsonResponse({'error': 'Invalid vendor name'}, status=400)

        product = get_object_or_404(MODELS_MAPPING[vendor_name], id=product_id, user_id=userid)
        product.active = True
        product.save()
        product_data = model_to_dict(product)

        general_product_data = self.map_vendor_data_to_general(vendor_name, product_data, userid)

        # Retrieve the User instance
        user = get_object_or_404(User, id=userid)
        general_product_data['user'] = user

        try:
            enrollment = VendoEnronment.objects.get(vendor_identifier = vendor_identifier)
        except VendoEnronment.DoesNotExist:
            return JsonResponse({'error': 'Vendor not found'}, status=404)
        

        general_product, created = Generalproducttable.objects.get_or_create(
            user=user,
            sku=general_product_data['sku'],
            enrollment= enrollment,
            product_id = product.id,
            defaults=general_product_data
        )

        if not created:
            # Update the existing record with new data
            for key, value in general_product_data.items():
                setattr(general_product, key, value)
            general_product.save()

        # Update the Generalproducttable instance with the data from the request
        serializer = GeneralProductSerializer(general_product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def map_vendor_data_to_general(self, vendor_name, product_data, userid):
        if vendor_name == 'lipsey':
            
            return {
                'user': userid,
                'vendor_name':vendor_name,
                'sku': product_data.get('itemnumber'),
                'quantity': product_data.get('quantity'),
                'upc': product_data.get('upc'),
                'title': product_data.get('description1'),
                'detailed_description': product_data.get('description2'),
                'image': product_data.get('imagename'),
                'category': product_data.get('type'),
                'msrp': product_data.get('msrp'),
                'mpn': product_data.get('manufacturermodelno'),
                'price': product_data.get('currentprice'),
                'model': product_data.get('model'),
                'manufacturer': product_data.get('manufacturer'),
                'shipping_weight': product_data.get('shippingweight'),
                'shipping_length': product_data.get('packagelength'),
                'shipping_width': product_data.get('packagewidth'),
                'shipping_height': product_data.get('packageheight'),
                'features': product_data.get('features'),
                'total_product_cost':product_data.get('total_product_cost')
            }
        elif vendor_name == 'cwr':
            return {
                'user': userid,
                'vendor_name':vendor_name,
                'sku': product_data.get('cwr_part_number'),
                'quantity': product_data.get('quantity_available_to_ship_combined'),
                'upc': product_data.get('upc_code'),
                'title': product_data.get('title'),
                'detailed_description': product_data.get('full_description'),
                'image': product_data.get('image_300x300_url'),
                'category': product_data.get('category_name'),
                'msrp': product_data.get('list_price'),
                'mpn': product_data.get('manufacturer_part_number'),
                'price': product_data.get('your_cost'),
                'model': None,  
                'brand': product_data.get('manufacturer_name'),
                'shipping_weight': product_data.get('shipping_weight'),
                'shipping_length': product_data.get('box_length'),
                'shipping_width': product_data.get('box_width'),
                'shipping_height': product_data.get('box_height'),
                'features': product_data.get('features'),
                'total_product_cost':product_data.get('total_product_cost')
            }

        elif vendor_name == 'fragrancex':
             return {
            'user': userid,
            'vendor_name':vendor_name,
            'sku': product_data.get('itemId'), 
            'title': product_data.get('productName'),  
            'detailed_description': product_data.get('description'),  
            'image': product_data.get('largeImageUrl'),
            'category': product_data.get('type'), 
            'msrp': product_data.get('retailPriceUSD'), 
            'price': product_data.get('wholesalePriceUSD'), 
            'upc': product_data.get('upc'), 
            'brand': product_data.get('brandName'),
            'quantity': product_data.get('quantityAvailable'),
            'features': product_data.get('features'),
            'total_product_cost':product_data.get('total_product_cost') 
           
        }

        elif vendor_name == 'ssi':
            return {
                'user': userid,
                'vendor_name':vendor_name,
                'sku': product_data.get('sku'),
                'title': product_data.get('description'),
                'detailed_description': product_data.get('detaileddescription'),
                'image': product_data.get('imageurl'),
                'category': product_data.get('category'),
                'msrp': product_data.get('msrp'),
                'map': product_data.get('map'),
                'price': product_data.get('price'),
                'upc': product_data.get('upccode'),
                'manufacturer': product_data.get('manufacturer'),
                'quantity': product_data.get('qty'),
                'model': product_data.get('mpn'),
                'dimensionh': product_data.get('dimensionh'),
                'dimensionl': product_data.get('dimensionl'),
                'dimensionw': product_data.get('dimensionw'),
                'shipping_weight': product_data.get('shippingweight'),
                'shipping_length': product_data.get('shippinglength'),
                'shipping_width': product_data.get('shippingwidth'),
                'shipping_height': product_data.get('shippingheight'),
                'features': product_data.get('features'),
                'total_product_cost':product_data.get('total_product_cost') 
            }
        elif vendor_name == 'zanders':
            return {
                'user': userid,
                'vendor_name':vendor_name,
                'sku': product_data.get('itemnumber'),
                'quantity': product_data.get('qty1'),
                'upc': product_data.get('upc'),
                'title': product_data.get('desc1'),
                'detailed_description': product_data.get('desc2'),
                'image': product_data.get('imagelink'),
                'category': product_data.get('category'),
                'msrp': product_data.get('msrp'),
                'mpn': product_data.get('mfgpnumber'),
                'map': product_data.get('mapprice'),
                'price': product_data.get('price1'),
                'brand': product_data.get('manufacturer'),
                'shipping_weight': product_data.get('weight'),
                'total_product_cost':product_data.get('total_product_cost') 
            }
        
        elif vendor_name == 'rsr':
            return {
                'user': userid,
                'vendor_name':vendor_name,
                'sku': product_data.get('sku'), 
                'quantity': product_data.get('inventory_on_hand'), 
                'upc': product_data.get('upc'),  
                'title': product_data.get('title'),  
                'detailed_description': product_data.get('description'),  
                'image': product_data.get('image_count'), 
                'category': product_data.get('category_name'),  
                'msrp': product_data.get('msrp'), 
                'mpn': product_data.get('manufacturer_part_number'), 
                'map': product_data.get('retail_map'), 
                'price': product_data.get('dealer_price'),  
                'brand': product_data.get('manufacturer_name'),  
                'shipping_weight': product_data.get('unit_weight'), 
                'shipping_length': product_data.get('unit_length'), 
                'shipping_width': product_data.get('unit_width'),  
                'shipping_height': product_data.get('unit_height'),  
                'model': product_data.get('manufacturer_code'),  
                'features': product_data.get('features'),
                'total_product_cost':product_data.get('total_product_cost') 
            }

        else:
            return {}

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def removeProduct(request, productId):
    try:
        product = Generalproducttable.objects.get(id = productId, user = request.user.id)
        product.delete()

        product_id = product.product_id
        vendor_name = product.enrollment.vendor_name
        product_model =MODELS_MAPPING[vendor_name.lower()]
        product_data = product_model.objects.get(id = product_id)
        product_data.active = False
        product_data.save()

        return JsonResponse({'message':'Product deleted successfully'})
    except Generalproducttable.DoesNotExist:
        return JsonResponse({'message': 'Product not found'}, status=404)

    except product_model.DoesNotExist:
        return JsonResponse({'message': 'Associated vendor product not found'}, status=404)

    except Exception as e:
        return JsonResponse({'message': str(e)}, status=500)

class ViewAllProducts(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GeneralProductSerializer
    pagination_class  = CataloguePagination
    

    def get_queryset(self):
        userid = self.kwargs['userid']
        return Generalproducttable.objects.filter(user_id=userid, active=False)

class ViewAllIdentifiers(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user.id
        vendor = VendoEnronment.objects.filter(user_id = user)
        serializer = VendoEnronmentSerializer(vendor, many=True)
        
        all_identifiers = []
        x = 1
        for item in serializer.data:
            dict_info = {
                'id':x,
                'vendor_identifier': item['vendor_identifier'],
            }
            all_identifiers.append(dict_info)
            x += 1

        return Response(all_identifiers, status=status.HTTP_200_OK)
    
class VendorIdentifiers(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_name):
        user = request.user.id
        vendor = VendoEnronment.objects.filter(user_id = user, vendor_name = vendor_name)
        serializer = VendoEnronmentSerializer(vendor, many=True)

        all_identifiers = []
        x = 1
        for item in serializer.data:
            dict_info = {
                'id':x,
                'vendor_identifier': item['vendor_identifier'],
            }
            all_identifiers.append(dict_info)
            x += 1


        return Response(all_identifiers, status=status.HTTP_200_OK)
    
class AllVendorEnrolled(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        user = request.user.id
        vendor = VendoEnronment.objects.filter(user_id = user)
        serializer = VendoEnronmentSerializer(vendor, many=True)

        vendor_enrolled = list({item['vendor_name'] for item in serializer.data})
        all_vendor_enrolled = []
        x = 1
        for item in vendor_enrolled:
            dict_info = {
                'id':x,
                'vendor_name': item,
                }
            all_vendor_enrolled.append(dict_info)
            x += 1


        return Response(all_vendor_enrolled, status=status.HTTP_200_OK)
