from . import models as _
import pandas as pd
from django.db import transaction

def map_vendor_data_to_general(vendor_name, product, user):
        if vendor_name == 'lipsey':
            
            return {
                'user': user,
                'vendor_name':vendor_name,
                'sku': product.product.sku,
                'quantity': product.quantity,
                'upc': product.product.upc,
                'title': product.product.description1,
                'detailed_description': product.product.description2,
                'image': product.product.imagename,
                'category': product.product.type,
                'msrp': product.product.msrp,
                'mpn': product.product.manufacturermodelno,
                'price': product.product.currentprice,
                'model': product.product.model,
                'manufacturer': product.product.manufacturer,
                'shipping_weight': product.product.shippingweight,
                'shipping_length': product.product.packagelength,
                'shipping_width': product.product.packagewidth,
                'shipping_height': product.product.packageheight,
                'features': product.product.features,
                'total_product_cost':product.total_price,
            }
        elif vendor_name == 'cwr':
            return {
                'user': user,
                'vendor_name':vendor_name,
                'sku': product.product.sku,
                'quantity': product.quantity,
                'upc': product.product.upc,
                'title': product.product.title,
                'detailed_description': product.product.full_description,
                'image': product.product.image_300x300_url,
                'category': product.product.category_name,
                'msrp': product.product.list_price,
                'mpn': product.product.manufacturer_part_number,
                'price': product.product.your_cost,
                'model': None,  
                'brand': product.product.manufacturer_name,
                'shipping_weight': product.product.shipping_weight,
                'shipping_length': product.product.box_length,
                'shipping_width': product.product.box_width,
                'shipping_height': product.product.box_height,
                'features': product.product.features,
                'total_product_cost':product.total_price,
            }

        elif vendor_name == 'fragrancex':
             return {
            'user': user,
            'vendor_name':vendor_name,
            'sku': product.product.sku, 
            'title': product.product.productName,  
            'detailed_description': product.product.description,  
            'image': product.product.largeImageUrl,
            'category': product.product.type, 
            'msrp': product.product.retailPriceUSD, 
            'price': product.product.wholesalePriceUSD, 
            'upc': product.product.upc, 
            'brand': product.product.brandName,
            'quantity': product.quantity,
            'features': product.product.features,
            'total_product_cost':product.total_price, 
           
        }

        elif vendor_name == 'ssi':
            return {
                'user': user,
                'vendor_name':vendor_name,
                'sku': product.product.sku,
                'title': product.product.description,
                'detailed_description': product.product.detaileddescription,
                'image': product.product.imageurl,
                'category': product.product.category,
                'msrp': product.product.msrp,
                'map': product.product.map,
                'price': product.product.price,
                'upc': product.product.upccode,
                'manufacturer': product.product.manufacturer,
                'quantity': product.quantity,
                'model': product.product.mpn,
                'dimensionh': product.product.dimensionh,
                'dimensionl': product.product.dimensionl,
                'dimensionw': product.product.dimensionw,
                'shipping_weight': product.product.shippingweight,
                'shipping_length': product.product.shippinglength,
                'shipping_width': product.product.shippingwidth,
                'shipping_height': product.product.shippingheight,
                'features': product.product.features,
                'total_product_cost':product.total_price,
            }
        elif vendor_name == 'zanders':
            return {
                'user': user,
                'vendor_name':vendor_name,
                'sku': product.product.sku,
                'quantity': product.quantity,
                'upc': product.product.upc,
                'title': product.product.desc1,
                'detailed_description': product.product.desc2,
                'image': product.product.imagelink,
                'category': product.product.category,
                'msrp': product.product.msrp,
                'mpn': product.product.mfgpnumber,
                'map': product.product.map,
                'price': product.product.price1,
                'brand': product.product.manufacturer,
                'shipping_weight': product.product.weight,
                'total_product_cost':product.total_price,
            }
        
        elif vendor_name == 'rsr':
            return {
                'user': user,
                'vendor_name':vendor_name,
                'sku': product.product.sku, 
                'quantity': product.quantity, 
                'upc': product.product.upc,  
                'title': product.product.title,  
                'detailed_description': product.product.description,  
                'image': product.product.image_count, 
                'category': product.product.category_name,  
                'msrp': product.product.msrp, 
                'mpn': product.product.manufacturer_part_number, 
                'map': product.product.map, 
                'price': product.product.dealer_price,  
                'brand': product.product.manufacturer_name,  
                'shipping_weight': product.product.unit_weight, 
                'shipping_length': product.product.unit_length, 
                'shipping_width': product.product.unit_width,  
                'shipping_height': product.product.unit_height,  
                'model': product.product.manufacturer_code,  
                'features': product.product.features,
                'total_product_cost':product.total_price,
            }

        else:
            return {}
            
def identifier_filter(Enrollment, vendor_name, identifier, userid, model, updateModel):
    """
    Filters the Enrollment model based on the vendor name and identifier.
    """
    
    try:
        if identifier is None:
            enrollment = Enrollment.objects.filter(user_id=userid, vendor__name=vendor_name).first()
            
        else:
            enrollment = Enrollment.objects.get(user_id=userid, vendor__name=vendor_name, identifier=identifier)
            
        if not enrollment:
            print("Enrollment is None skipping processing.")
            return model.objects.none()
        
    except Enrollment.DoesNotExist:
        return model.objects.none()

    filters = {'account__user_id': userid, 'active': False}
    vendor = vendor_name.lower()

    if vendor == 'lipsey':
        if enrollment.product_filter:
            filters['product__itemtype__in'] = enrollment.product_filter
        if enrollment.manufacturer:
            filters['product__manufacturer__in'] = enrollment.manufacturer
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    elif vendor == 'fragrancex':
        if enrollment.brand:
            filters['product__brandName__in'] = enrollment.brand
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    elif vendor == 'rsr':
        if enrollment.product_category:
            filters['product__category_name__in'] = enrollment.product_category
        if enrollment.manufacturer:
            filters['product__manufacturer_name__in'] = enrollment.manufacturer
        if enrollment.shippable:
            filters['product__drop_shippable__in'] = enrollment.shippable
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    elif vendor == 'cwr':
        if not enrollment.returnable:
            filters['product__returnable'] = True
            
        # if not enrollment.third_party_marketplaces:
        #     filters['product__number_3rd_party_marketplaces'] = True
        
        if not enrollment.oversized:
            filters['product__oversized'] = False
        
        if not enrollment.truck_freight:
            filters['product__truck_freight'] = False
        
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    elif vendor == 'ssi':
        if enrollment.product_category:
            filters['product__category__in'] = enrollment.product_category
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    elif vendor == 'zanders':
        filters['product__serialized'] = 'Yes' if enrollment.serialized else 'No'
        if enrollment.manufacturer:
            filters['product__manufacturer__in'] = enrollment.manufacturer
        if enrollment.stock_minimum != 1:
            filters['quantity__gte'] = enrollment.stock_minimum

    return updateModel.objects.filter(**filters).select_related('product').order_by('created_at')
    
class VendorDataMixin:
    vendor_models = {
        'fragrancex': (_.Fragrancex, _.FragrancexUpdate),
        'lipsey': (_.Lipsey, _.LipseyUpdate),
        'cwr': (_.Cwr, _.CwrUpdate),
        'rsr': (_.Rsr, _.RsrUpdate),
        'zanders': (_.Zanders, _.ZandersUpdate),
    }

    vendor_id_fields = {
        'fragrancex': 'sku',
        'lipsey': 'sku',
        'rsr': 'sku',
        'cwr': 'sku',
        'zanders': 'sku',
    }

    vendor_mpn_fields = {
        'fragrancex': 'mpn',
        'lipsey': 'manufacturermodelno',
        'rsr': 'manufacturer_part_number',
        'cwr': 'manufacturer_part_number',
        'zanders': 'mfgpnumber',
    }

    def get_vendor_config(self, vendor_name):
        vendor_name = vendor_name.lower()
        if vendor_name not in self.vendor_models:
            raise ValueError(f"Unsupported vendor: {vendor_name}")
        return {
            'vendor_name': vendor_name,
            'model': self.vendor_models[vendor_name][0],
            'update_model': self.vendor_models[vendor_name][1],
            'id_field': self.vendor_id_fields[vendor_name],
            'mpn_field': self.vendor_mpn_fields[vendor_name],
        }

    def product_matches_filters(self, product, enrollment, vendor_name):
        if vendor_name == 'lipsey':
            if enrollment.product_filter and product.itemtype not in enrollment.product_filter:
                return False
            if enrollment.manufacturer and product.manufacturer not in enrollment.manufacturer:
                return False
        elif vendor_name == 'fragrancex':
            if enrollment.brand and product.brandName not in enrollment.brand:
                return False
        elif vendor_name == 'rsr':
            if enrollment.product_category and product.category_name not in enrollment.product_category:
                return False
            if enrollment.manufacturer and product.manufacturer_name not in enrollment.manufacturer:
                return False
            if enrollment.shippable and product.drop_shippable not in enrollment.shippable:
                return False
        elif vendor_name == 'cwr':
            if product.returnable == False:
                if enrollment.returnable == False:
                    return False
            
            # if product.number_3rd_party_marketplaces == False:
            #     if enrollment.third_party_marketplaces == False:
            #         return False
                
            if product.oversized == True:
                if enrollment.oversized == False:
                    return False
                
            if product.truck_freight == True:
                if enrollment.truck_freight == False:
                    return False
        elif vendor_name == 'ssi':
            if enrollment.product_category and product.category not in enrollment.product_category:
                return False
        elif vendor_name == 'zanders':
            if product.serialized != ('Yes' if enrollment.serialized else 'No'):
                return False
            if enrollment.manufacturer and product.manufacturer not in enrollment.manufacturer:
                return False
        return True

    def process_vendor_update(
        self,
        file_path,
        enrollment,
        model,
        model_update,
        id_column_name,
        price_column_name,
        qty_column_name
    ):
        df = pd.read_csv(file_path)

        df[price_column_name] = pd.to_numeric(df[price_column_name], errors='coerce').fillna(0.0)
        df[qty_column_name] = pd.to_numeric(df[qty_column_name], downcast='integer', errors='coerce').fillna(0).astype(int)
        df[id_column_name] = df[id_column_name].astype(str)

        config = self.get_vendor_config(enrollment.vendor.name)
        id_field = config['id_field']
        mpn_field = config['mpn_field']
        supplier_name = config['vendor_name']

        item_ids = df[id_column_name].tolist()
        product_qs = model.objects.filter(**{f"{id_field}__in": item_ids})
        product_map = {getattr(p, id_field): p for p in product_qs}

        update_qs = model_update.objects.filter(product__in=product_qs, account=enrollment.account)
        update_map = {u.product.id: u for u in update_qs}

        fixed_markup = float(enrollment.fixed_markup)
        percentage_markup = float(enrollment.percentage_markup)
        shipping_cost = float(enrollment.shipping_cost)
        shipping_cost_avg = enrollment.shipping_cost_average

        updates = []
        new_entries = []

        for _, row in df.iterrows():
            item_id = str(row[id_column_name])
            price = row[price_column_name]
            quantity = row[qty_column_name]
            product = product_map.get(item_id)

            if not product or not self.product_matches_filters(product, enrollment, supplier_name):
                continue

            shipping = float(product.avgshipcost or 0) if shipping_cost_avg else shipping_cost
            total_price = round(price + fixed_markup + ((percentage_markup / 100) * price) + shipping, 2)

            existing = update_map.get(product.id)
            if existing:
                existing.price = price
                existing.quantity = quantity
                existing.total_price = total_price
                updates.append(existing)
            else:
                new_entries.append(
                    model_update(
                        product=product,
                        upc=getattr(product, 'upc', None),
                        sku=getattr(product, id_field, None),
                        mpn=getattr(product, mpn_field, None),
                        account=enrollment.account,
                        vendor=enrollment.vendor,
                        price=price,
                        quantity=quantity,
                        total_price=total_price
                    )
                )

        with transaction.atomic():
            if updates:
                model_update.objects.bulk_update(updates, ['price', 'quantity', 'total_price'], batch_size=500)
            if new_entries:
                model_update.objects.bulk_create(new_entries, batch_size=500)

        print(f"Processed {len(updates)} updates and {len(new_entries)} new entries.")
