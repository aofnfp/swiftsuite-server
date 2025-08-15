from django.db import models
from accounts.models import User

# Create your models here.

class VendoEnronment(models.Model):
    vendor_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vendor_name = models.CharField(max_length=30, unique=False, null=False)
    address_street1 = models.CharField(max_length=150, null=False, unique=False)
    address_street2 = models.CharField(max_length=150, null=True, unique=False)
    city = models.CharField(max_length=50, null=False, unique=False)
    state = models.CharField(max_length=50, null=False, unique=False)
    zip_code = models.CharField(max_length=50, null=False, unique=False)
    country = models.CharField(max_length=50, null=False, unique=False)
    ftp_username = models.CharField(max_length=50, null=True, unique=False)
    ftp_password = models.CharField(max_length=50, null=True, unique=False)
    ftp_url = models.CharField(max_length=255, null=True, blank=True)
    file_urls = models.TextField(null=True, blank=True)
    host = models.CharField(max_length=255, null=True, blank=True)
    apiAccessId = models.CharField(max_length=255, null=True)
    apiAccessKey = models.CharField(max_length=255, null=True)
    Username = models.CharField(max_length=255, null=True)
    Password = models.CharField(max_length=255, null=True)
    POS = models.CharField(max_length=255, null=True)
    vendor_identifier = models.CharField(max_length=50, unique=True, null=True)

    # Price options
    percentage_markup = models.TextField(blank=True, null=True)
    fixed_markup = models.TextField(blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    shipping_cost_average = models.BooleanField(default=False)
    stock_minimum = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock_maximum = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    update_inventory = models.BooleanField(default=False)
    send_orders = models.BooleanField(default=False)
    update_tracking = models.BooleanField(default=False)

    # Product Filters
    product_filter = models.JSONField(blank=True, null=True, default=list)
    product_category = models.JSONField(blank=True, null=True, default=list)
    brand = models.JSONField(blank=True, null=True, default=list)
    manufacturer = models.JSONField(blank=True, null=True, default=list)
    shippable = models.JSONField(blank=True, null=True, default=list)

    # Zander Field
    serialized = models.BooleanField(default=False)

    # CWR Fields
    truck_freight = models.BooleanField(default=False) 
    oversized = models.BooleanField(default=False)
    third_party_marketplaces = models.BooleanField(default=False)
    returnable = models.BooleanField(default=False)

class Cwr(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cwr_part_number = models.TextField(unique=True,  blank=True, null=True)
    manufacturer_part_number = models.TextField(blank=True, null=True)
    upc_code = models.TextField(blank=True, null=True)
    quantity_available_to_ship_combined = models.TextField(blank=True, null=True)
    quantity_available_to_ship_nj = models.TextField(blank=True, null=True)
    quantity_available_to_ship_fl = models.TextField(blank=True, null=True)
    next_shipment_date_combined = models.TextField(blank=True, null=True)
    next_shipment_date_nj = models.TextField(blank=True, null=True)
    next_shipment_date_fl = models.TextField(blank=True, null=True)
    your_cost = models.TextField(blank=True, null=True)
    list_price = models.TextField(blank=True, null=True)
    m_a_p_price = models.TextField(blank=True, null=True)
    m_r_p_price = models.TextField(blank=True, null=True)
    uppercase_title = models.TextField(db_column='Uppercase Title', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    title = models.TextField(db_column='Title', blank=True, null=True)  # Field name made lowercase.
    full_description = models.TextField(db_column='Full Description', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    category_id = models.TextField(blank=True, null=True)
    category_name = models.TextField(db_column='Category Name', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    manufacturer_name = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    shipping_weight = models.TextField(blank=True, null=True)
    box_height = models.TextField(blank=True, null=True)
    box_length = models.TextField(blank=True, null=True)
    box_width = models.TextField(blank=True, null=True)
    list_of_accessories_by_sku = models.TextField(db_column='List of Accessories by SKU', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    list_of_accessories_by_mfg = models.TextField(db_column='List of Accessories by MFG#', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    quick_specs = models.TextField(db_column='Quick Specs', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    image_300x300_url = models.TextField(db_column='Image (300x300) Url', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    image_1000x1000_url = models.TextField(db_column='Image (1000x1000) Url', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    non_stock = models.TextField(blank=True, null=True)
    drop_ships_direct_from_vendor = models.TextField(blank=True, null=True)
    hazardous_materials = models.TextField(blank=True, null=True)
    truck_freight = models.BooleanField(blank=True, null=True)
    exportable = models.TextField(blank=True, null=True)
    first_class_mail = models.TextField(blank=True, null=True)
    oversized = models.BooleanField(blank=True, null=True)
    remanufactured = models.TextField(blank=True, null=True)
    closeout = models.TextField(blank=True, null=True)
    harmonization_code = models.TextField( blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    country_of_origin = models.TextField( blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    sale = models.TextField(blank=True, null=True)
    original_price_if_on_sale_closeout = models.TextField(blank=True, null=True)
    sale_start_date = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    sale_end_date = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    rebate = models.TextField(db_column='Rebate', blank=True, null=True)  # Field name made lowercase.
    rebate_description = models.TextField(db_column='Rebate Description', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    rebate_start_date = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    rebate_end_date = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    google_merchant_category = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    quick_guide_literature_pdf_url = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    owners_manual_pdf_url = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    brochure_literature_pdf_url = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    installation_guide_pdf_url = models.TextField(blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    video_urls = models.TextField(db_column='Video Urls', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    prop_65 = models.TextField(blank=True, null=True)
    prop_65_description = models.TextField(db_column='Prop 65 Description', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    free_shipping = models.TextField(blank=True, null=True)
    free_shipping_end_date = models.TextField(db_column='Free Shipping End Date', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    returnable = models.BooleanField(blank=True, null=True)
    image_additional_1000x1000_urls = models.TextField(db_column='Image Additional (1000x1000) Urls', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    case_qty_nj = models.TextField(blank=True, null=True)
    case_qty_fl = models.TextField(blank=True, null=True)
    number_3rd_party_marketplaces = models.BooleanField(db_column='3rd Party Marketplaces', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it wasn't a valid Python identifier.
    fcc_id = models.TextField(db_column='FCC ID', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    sku = models.TextField(blank=True, null=True)
    mfgn = models.TextField(blank=True, null=True)
    qty = models.TextField(blank=True, null=True)
    qtynj = models.TextField(blank=True, null=True)
    qtyfl = models.TextField(blank=True, null=True)
    price = models.TextField(blank=True, null=True)
    map = models.TextField(blank=True, null=True)
    mrp = models.TextField(blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)

class Fragrancex(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    itemId = models.CharField(db_column='ITEM_ID', max_length=255, blank=True, null=True)  
    productName = models.CharField(db_column='PRODUCT_NAME', max_length=255, blank=True, null=True)  
    description = models.TextField(db_column='DESCRIPTION', blank=True, null=True)  
    brandName = models.CharField(db_column='BRAND_NAME', max_length=255, blank=True, null=True)  
    gender = models.CharField(db_column='GENDER', max_length=255, blank=True, null=True)  ###
    size = models.CharField(db_column='SIZE', max_length=255, blank=True, null=True)  ###
    metric_size = models.CharField(db_column='METRIC_SIZE', max_length=255, blank=True, null=True)  ###
    retailPriceUSD = models.CharField(db_column='RETAIL_PRICE_USD', max_length=255, blank=True, null=True)  
    wholesalePriceUSD = models.CharField(db_column='WHOLESALE_PRICE_USD', max_length=255, blank=True, null=True)  
    wholesalePriceEUR = models.CharField(db_column='WHOLESALE_PRICE_EUR', max_length=255, blank=True, null=True)  
    wholesalePriceGBP = models.CharField(db_column='WHOLESALE_PRICE_GBP', max_length=255, blank=True, null=True)  
    wholesalePriceCAD = models.CharField(db_column='WHOLESALE_PRICE_CAD', max_length=255, blank=True, null=True)  
    wholesalePriceAUD = models.CharField(db_column='WHOLESALE_PRICE_AUD', max_length=255, blank=True, null=True)  
    smallImageUrl = models.CharField(db_column='SMALL_IMAGE_URL', max_length=255, blank=True, null=True)  
    largeImageUrl = models.CharField(db_column='LARGE_IMAGE_URL', max_length=255, blank=True, null=True)  
    type = models.CharField(db_column='TYPE', max_length=255, blank=True, null=True)  ###
    quantityAvailable = models.CharField(db_column='QUANTITY_AVAILABLE', max_length=255, blank=True, null=True)  
    upc = models.CharField(db_column='UPC', max_length=255, blank=True, null=True)  
    instock = models.CharField(db_column='INSTOCK', max_length=255, blank=True, null=True)  
    parentCode = models.CharField(db_column='PARENT_CODE', max_length=255, blank=True, null=True)  
    features = models.TextField(db_column='Features', blank=True, null=True)
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)


class Generalproducttable(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product_id = models.TextField(null=True)
    enrollment = models.ForeignKey(VendoEnronment, on_delete=models.CASCADE, null=True)
    vendor_name = models.CharField(max_length=255, null=True)
    sku = models.CharField(db_column='SKU', max_length=255, blank=True, null=True)  # Field name made lowercase.
    quantity = models.TextField(db_column='Quantity', blank=True, null=True)  # Field name made lowercase.
    upc = models.CharField(db_column='UPC', max_length=255, blank=True, null=True)  # Field name made lowercase.
    title = models.CharField(db_column='Title', max_length=255, blank=True, null=True)  # Field name made lowercase.
    detailed_description = models.TextField(db_column='Detailed_Description', blank=True, null=True)  # Field name made lowercase.
    image = models.CharField(db_column='Image', max_length=255, blank=True, null=True)  # Field name made lowercase.
    category = models.CharField(db_column='Category', max_length=255, blank=True, null=True)  # Field name made lowercase.
    category_id = models.IntegerField(db_column='Category_ID', blank=True, null=True)  # Field name made lowercase.
    msrp = models.TextField(db_column='MSRP', blank=True, null=True)  # Field name made lowercase.
    mpn = models.CharField(db_column='MPN', max_length=255, blank=True, null=True)  # Field name made lowercase.
    map = models.TextField(db_column='MAP', blank=True, null=True)  # Field name made lowercase.
    dimensionh = models.DecimalField(db_column='DimensionH', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    dimensionl = models.DecimalField(db_column='DimensionL', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    dimensionw = models.DecimalField(db_column='DimensionW', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    shipping_weight = models.DecimalField(db_column='Shipping_Weight', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    shipping_length = models.DecimalField(db_column='Shipping_Length', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    shipping_width = models.DecimalField(db_column='Shipping_Width', max_digits=10, decimal_places=6, blank=True, null=True)  # Field name made lowercase.
    shipping_height = models.TextField(db_column='Shipping_Height', blank=True, null=True)  # Field name made lowercase.
    model = models.CharField(db_column='Model', max_length=255, blank=True, null=True)  # Field name made lowercase.
    price = models.TextField(db_column='Price', blank=True, null=True)  # Field name made lowercase.
    brand = models.CharField(db_column='Brand', max_length=255, blank=True, null=True)  # Field name made lowercase.
    manufacturer = models.CharField(db_column='Manufacturer', max_length=255, blank=True, null=True)  # Field name made lowercase.
    prop_65 = models.IntegerField(db_column='Prop_65', blank=True, null=True)  # Field name made lowercase.
    prop_65_description = models.TextField(db_column='Prop_65_Description', blank=True, null=True)  # Field name made lowercase.
    manufacturer_id = models.IntegerField(db_column='Manufacturer_Id', blank=True, null=True)  # Field name made lowercase.
    date_created = models.DateField(db_column='Date_Created', blank=True, null=True)  # Field name made lowercase.
    thumbnail = models.CharField(db_column='Thumbnail', max_length=255, blank=True, null=True)  # Field name made lowercase.  
    features = models.TextField(db_column='Features', blank=True, null=True)  
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)


class Lipsey(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    itemnumber = models.TextField(db_column='ItemNumber', blank=True, null=True)  # Field name made lowercase.
    description1 = models.TextField(db_column='Description1', blank=True, null=True)  # Field name made lowercase.
    description2 = models.TextField(db_column='Description2', blank=True, null=True)  # Field name made lowercase.
    upc = models.TextField(db_column='Upc', blank=True, null=True)  # Field name made lowercase.
    manufacturermodelno = models.TextField(db_column='ManufacturerModelNo', blank=True, null=True)  # Field name made lowercase.
    msrp = models.TextField(db_column='Msrp', blank=True, null=True)  # Field name made lowercase.
    model = models.TextField(db_column='Model', blank=True, null=True)  # Field name made lowercase.
    calibergauge = models.TextField(db_column='CaliberGauge', blank=True, null=True)  # Field name made lowercase.
    manufacturer = models.TextField(db_column='Manufacturer', blank=True, null=True)  # Field name made lowercase.
    type = models.TextField(db_column='Type', blank=True, null=True)  # Field name made lowercase.
    action = models.TextField(db_column='Action', blank=True, null=True)  # Field name made lowercase.
    barrellength = models.TextField(db_column='BarrelLength', blank=True, null=True)  # Field name made lowercase.
    capacity = models.TextField(db_column='Capacity', blank=True, null=True)  # Field name made lowercase.
    finish = models.TextField(db_column='Finish', blank=True, null=True)  # Field name made lowercase.
    overalllength = models.TextField(db_column='OverallLength', blank=True, null=True)  # Field name made lowercase.
    receiver = models.TextField(db_column='Receiver', blank=True, null=True)  # Field name made lowercase.
    safety = models.TextField(db_column='Safety', blank=True, null=True)  # Field name made lowercase.
    sights = models.TextField(db_column='Sights', blank=True, null=True)  # Field name made lowercase.
    stockframegrips = models.TextField(db_column='StockFrameGrips', blank=True, null=True)  # Field name made lowercase.
    magazine = models.TextField(db_column='Magazine', blank=True, null=True)  # Field name made lowercase.
    weight = models.TextField(db_column='Weight', blank=True, null=True)  # Field name made lowercase.
    imagename = models.TextField(db_column='ImageName', blank=True, null=True)  # Field name made lowercase.
    chamber = models.TextField(db_column='Chamber', blank=True, null=True)  # Field name made lowercase.
    drilledandtapped = models.TextField(db_column='DrilledAndTapped', blank=True, null=True)  # Field name made lowercase.
    rateoftwist = models.TextField(db_column='RateOfTwist', blank=True, null=True)  # Field name made lowercase.
    itemtype = models.TextField(db_column='ItemType', blank=True, null=True)  # Field name made lowercase.
    additionalfeature1 = models.TextField(db_column='AdditionalFeature1', blank=True, null=True)  # Field name made lowercase.
    additionalfeature2 = models.TextField(db_column='AdditionalFeature2', blank=True, null=True)  # Field name made lowercase.
    additionalfeature3 = models.TextField(db_column='AdditionalFeature3', blank=True, null=True)  # Field name made lowercase.
    shippingweight = models.TextField(db_column='ShippingWeight', blank=True, null=True)  # Field name made lowercase.
    boundbookmanufacturer = models.TextField(db_column='BoundBookManufacturer', blank=True, null=True)  # Field name made lowercase.
    boundbookmodel = models.TextField(db_column='BoundBookModel', blank=True, null=True)  # Field name made lowercase.
    boundbooktype = models.TextField(db_column='BoundBookType', blank=True, null=True)  # Field name made lowercase.
    nfathreadpattern = models.TextField(db_column='NfaThreadPattern', blank=True, null=True)  # Field name made lowercase.
    nfaattachmentmethod = models.TextField(db_column='NfaAttachmentMethod', blank=True, null=True)  # Field name made lowercase.
    nfabaffletype = models.TextField(db_column='NfaBaffleType', blank=True, null=True)  # Field name made lowercase.
    silencercanbedisassembled = models.TextField(db_column='SilencerCanBeDisassembled', blank=True, null=True)  # Field name made lowercase.
    silencerconstructionmaterial = models.TextField(db_column='SilencerConstructionMaterial', blank=True, null=True)  # Field name made lowercase.
    nfadbreduction = models.TextField(db_column='NfaDbReduction', blank=True, null=True)  # Field name made lowercase.
    silenceroutsidediameter = models.TextField(db_column='SilencerOutsideDiameter', blank=True, null=True)  # Field name made lowercase.
    nfaform3caliber = models.TextField(db_column='NfaForm3Caliber', blank=True, null=True)  # Field name made lowercase.
    opticmagnification = models.TextField(db_column='OpticMagnification', blank=True, null=True)  # Field name made lowercase.
    maintubesize = models.TextField(db_column='MaintubeSize', blank=True, null=True)  # Field name made lowercase.
    adjustableobjective = models.TextField(db_column='AdjustableObjective', blank=True, null=True)  # Field name made lowercase.
    objectivesize = models.TextField(db_column='ObjectiveSize', blank=True, null=True)  # Field name made lowercase.
    opticadjustments = models.TextField(db_column='OpticAdjustments', blank=True, null=True)  # Field name made lowercase.
    illuminatedreticle = models.TextField(db_column='IlluminatedReticle', blank=True, null=True)  # Field name made lowercase.
    reticle = models.TextField(db_column='Reticle', blank=True, null=True)  # Field name made lowercase.
    exclusive = models.TextField(db_column='Exclusive', blank=True, null=True)  # Field name made lowercase.
    quantity = models.TextField(db_column='Quantity', blank=True, null=True)  # Field name made lowercase.
    allocated = models.TextField(db_column='Allocated', blank=True, null=True)  # Field name made lowercase.
    onsale = models.TextField(db_column='OnSale', blank=True, null=True)  # Field name made lowercase.
    price = models.TextField(db_column='Price', blank=True, null=True)  # Field name made lowercase.
    currentprice = models.TextField(db_column='CurrentPrice', blank=True, null=True)  # Field name made lowercase.
    retailmap = models.TextField(db_column='RetailMap', blank=True, null=True)  # Field name made lowercase.
    fflrequired = models.TextField(db_column='FflRequired', blank=True, null=True)  # Field name made lowercase.
    sotrequired = models.TextField(db_column='SotRequired', blank=True, null=True)  # Field name made lowercase.
    exclusivetype = models.TextField(db_column='ExclusiveType', blank=True, null=True)  # Field name made lowercase.
    scopecoverincluded = models.TextField(db_column='ScopeCoverIncluded', blank=True, null=True)  # Field name made lowercase.
    special = models.TextField(db_column='Special', blank=True, null=True)  # Field name made lowercase.
    sightstype = models.TextField(db_column='SightsType', blank=True, null=True)  # Field name made lowercase.
    case = models.TextField(db_column='Case', blank=True, null=True)  # Field name made lowercase.
    choke = models.TextField(db_column='Choke', blank=True, null=True)  # Field name made lowercase.
    dbreduction = models.TextField(db_column='DbReduction', blank=True, null=True)  # Field name made lowercase.
    family = models.TextField(db_column='Family', blank=True, null=True)  # Field name made lowercase.
    finishtype = models.TextField(db_column='FinishType', blank=True, null=True)  # Field name made lowercase.
    frame = models.TextField(db_column='Frame', blank=True, null=True)  # Field name made lowercase.
    griptype = models.TextField(db_column='GripType', blank=True, null=True)  # Field name made lowercase.
    handgunslidematerial = models.TextField(db_column='HandgunSlideMaterial', blank=True, null=True)  # Field name made lowercase.
    countryoforigin = models.TextField(db_column='CountryOfOrigin', blank=True, null=True)  # Field name made lowercase.
    itemlength = models.TextField(db_column='ItemLength', blank=True, null=True)  # Field name made lowercase.
    itemwidth = models.TextField(db_column='ItemWidth', blank=True, null=True)  # Field name made lowercase.
    itemheight = models.TextField(db_column='ItemHeight', blank=True, null=True)  # Field name made lowercase.
    packagelength = models.TextField(db_column='PackageLength', blank=True, null=True)  # Field name made lowercase.
    packagewidth = models.TextField(db_column='PackageWidth', blank=True, null=True)  # Field name made lowercase.
    packageheight = models.TextField(db_column='PackageHeight', blank=True, null=True)  # Field name made lowercase.
    itemgroup = models.TextField(db_column='ItemGroup', blank=True, null=True)  # Field name made lowercase.
    features = models.TextField(db_column='Features', blank=True, null=True)
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)


class Rsr(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sku = models.TextField(db_column='SKU', blank=True, null=True)  # SKU
    last_modified = models.DateTimeField(db_column='Last_Modified', blank=True, null=True)  # LastModified
    upc = models.TextField(db_column='UPC', blank=True, null=True)  # UPC
    title = models.TextField(db_column='Title', blank=True, null=True)  # Title
    description = models.TextField(db_column='Description', blank=True, null=True)  # Description
    manufacturer_code = models.TextField(db_column='Manufacturer_Code', blank=True, null=True)  # ManufacturerCode
    manufacturer_name = models.TextField(db_column='Manufacturer_Name', blank=True, null=True)  # ManufacturerName
    manufacturer_part_number = models.TextField(db_column='Manufacturer_Part_Number', blank=True, null=True)  # ManufacturerPartNumber
    department_id = models.TextField(db_column='Department_ID', blank=True, null=True)  # DepartmentId
    department_name = models.TextField(db_column='Department_Name', blank=True, null=True)  # DepartmentName
    category_id = models.TextField(db_column='Category_ID', blank=True, null=True)  # CategoryId
    category_name = models.TextField(db_column='Category_Name', blank=True, null=True)  # CategoryName
    subcategory_name = models.TextField(db_column='Subcategory_Name', blank=True, null=True)  # SubcategoryName
    exclusive = models.CharField(max_length=1, db_column='Exclusive', blank=True, null=True)  # Exclusive
    talo_exclusive = models.CharField(max_length=1, db_column='Talo_Exclusive', blank=True, null=True)  # TaloExclusive
    coming_soon = models.CharField(max_length=1, db_column='Coming_Soon', blank=True, null=True)  # ComingSoon
    new_item = models.CharField(max_length=1, db_column='New_Item', blank=True, null=True)  # NewItem
    le_resale_only = models.CharField(max_length=1, db_column='LE_Resale_Only', blank=True, null=True)  # LEResaleOnly
    unit_of_measure = models.TextField(db_column='Unit_of_Measure', blank=True, null=True)  # UnitOfMeasure
    items_per_case = models.IntegerField(db_column='Items_Per_Case', blank=True, null=True)  # ItemsPerCase
    items_per_unit = models.IntegerField(db_column='Items_Per_Unit', blank=True, null=True)  # ItemsPerUnit
    units_per_case = models.IntegerField(db_column='Units_Per_Case', blank=True, null=True)  # UnitsPerCase
    nfa = models.CharField(max_length=1, db_column='NFA', blank=True, null=True)  # NFA
    hazard_warning = models.TextField(db_column='Hazard_Warning', blank=True, null=True)  # HazardWarning
    image_count = models.IntegerField(db_column='Image_Count', blank=True, null=True)  # ImageCount
    msrp = models.DecimalField(max_digits=10, decimal_places=2, db_column='MSRP', blank=True, null=True)  # MSRP
    retail_map = models.DecimalField(max_digits=10, decimal_places=2, db_column='Retail_MAP', blank=True, null=True)  # RetailMAP
    inventory_on_hand = models.IntegerField(db_column='Inventory_On_Hand', blank=True, null=True)  # InventoryOnHand
    ground_only = models.CharField(max_length=1, db_column='Ground_Only', blank=True, null=True)  # GroundOnly
    drop_ship_block = models.CharField(max_length=1, db_column='Drop_Ship_Block', blank=True, null=True)  # DropShipBlock
    closeout = models.CharField(max_length=1, db_column='Closeout', blank=True, null=True)  # Closeout
    allocated = models.CharField(max_length=1, db_column='Allocated', blank=True, null=True)  # Allocated
    drop_shippable = models.CharField(max_length=1, db_column='Drop_Shippable', blank=True, null=True)  # DropShippable
    unit_weight = models.DecimalField(max_digits=10, decimal_places=2, db_column='Unit_Weight', blank=True, null=True)  # UnitWeight
    unit_length = models.DecimalField(max_digits=10, decimal_places=2, db_column='Unit_Length', blank=True, null=True)  # UnitLength
    unit_width = models.DecimalField(max_digits=10, decimal_places=2, db_column='Unit_Width', blank=True, null=True)  # UnitWidth
    unit_height = models.DecimalField(max_digits=10, decimal_places=2, db_column='Unit_Height', blank=True, null=True)  # UnitHeight
    case_weight = models.DecimalField(max_digits=10, decimal_places=2, db_column='Case_Weight', blank=True, null=True)  # CaseWeight
    case_length = models.DecimalField(max_digits=10, decimal_places=2, db_column='Case_Length', blank=True, null=True)  # CaseLength
    case_width = models.DecimalField(max_digits=10, decimal_places=2, db_column='Case_Width', blank=True, null=True)  # CaseWidth
    case_height = models.DecimalField(max_digits=10, decimal_places=2, db_column='Case_Height', blank=True, null=True)  # CaseHeight
    blemished = models.CharField(max_length=1, db_column='Blemished', blank=True, null=True)  # Blemished
    dealer_price = models.DecimalField(max_digits=10, decimal_places=2, db_column='Dealer_Price', blank=True, null=True)  # DealerPrice
    dealer_case_price = models.DecimalField(max_digits=10, decimal_places=2, db_column='Dealer_Case_Price', blank=True, null=True)  # DealerCasePrice
    features = models.TextField(db_column='Features', blank=True, null=True)  
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)
    images = models.TextField(null=True)

    
class Ssi(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sku = models.CharField(db_column='SKU', max_length=255, blank=True, null=True)  # Field name made lowercase.
    description = models.CharField(db_column='Description', max_length=255, blank=True, null=True)  # Field name made lowercase.
    datecreated = models.CharField(db_column='DateCreated', max_length=255, blank=True, null=True)  # Field name made lowercase.
    dimensionh = models.CharField(db_column='DimensionH', max_length=255, blank=True, null=True)  # Field name made lowercase.
    dimensionl = models.CharField(db_column='DimensionL', max_length=255, blank=True, null=True)  # Field name made lowercase.
    dimensionw = models.CharField(db_column='DimensionW', max_length=255, blank=True, null=True)  # Field name made lowercase.
    manufacturer = models.CharField(db_column='Manufacturer', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imageurl = models.CharField(db_column='ImageURL', max_length=255, blank=True, null=True)  # Field name made lowercase.
    thumbnailurl = models.CharField(db_column='ThumbnailURL', max_length=255, blank=True, null=True)  # Field name made lowercase.
    upccode = models.CharField(db_column='UPCCode', max_length=255, blank=True, null=True)  # Field name made lowercase.
    weight = models.CharField(db_column='Weight', max_length=255, blank=True, null=True)  # Field name made lowercase.
    weightunits = models.CharField(db_column='WeightUnits', max_length=255, blank=True, null=True)  # Field name made lowercase.
    category = models.CharField(db_column='Category', max_length=255, blank=True, null=True)  # Field name made lowercase.
    subcategory = models.CharField(db_column='Subcategory', max_length=255, blank=True, null=True)  # Field name made lowercase.
    status = models.CharField(db_column='Status', max_length=255, blank=True, null=True)  # Field name made lowercase.
    map = models.CharField(db_column='MAP', max_length=255, blank=True, null=True)  # Field name made lowercase.
    msrp = models.CharField(db_column='MSRP', max_length=255, blank=True, null=True)  # Field name made lowercase.
    mpn = models.CharField(db_column='MPN', max_length=255, blank=True, null=True)  # Field name made lowercase.
    minimumorderquantity = models.CharField(db_column='MinimumOrderQuantity', max_length=255, blank=True, null=True)  # Field name made lowercase.
    detaileddescription = models.TextField(db_column='DetailedDescription', blank=True, null=True)  # Field name made lowercase.
    shippingweight = models.CharField(db_column='ShippingWeight', max_length=255, blank=True, null=True)  # Field name made lowercase.
    shippinglength = models.CharField(db_column='ShippingLength', max_length=255, blank=True, null=True)  # Field name made lowercase.
    shippingwidth = models.CharField(db_column='ShippingWidth', max_length=255, blank=True, null=True)  # Field name made lowercase.
    shippingheight = models.CharField(db_column='ShippingHeight', max_length=255, blank=True, null=True)  # Field name made lowercase.
    attribute1 = models.TextField(blank=True, null=True)
    attribute2 = models.TextField(blank=True, null=True)
    attribute3 = models.TextField(blank=True, null=True)
    attribute4 = models.TextField(blank=True, null=True)
    attribute5 = models.TextField(blank=True, null=True)
    attribute6 = models.TextField(blank=True, null=True)
    attribute7 = models.TextField(blank=True, null=True)
    prop65warning = models.CharField(max_length=255, blank=True, null=True)
    prop65reason = models.TextField(blank=True, null=True)
    countryoforigin = models.TextField(blank=True, null=True)
    groundshippingrequired = models.TextField(blank=True, null=True)
    price = models.CharField(db_column='Price', max_length=255, blank=True, null=True)  # Field name made lowercase.
    avgshipcost = models.TextField(blank=True, null=True)
    qty = models.CharField(db_column='Qty', max_length=255, blank=True, null=True)  # Field name made lowercase.
    features = models.TextField(db_column='Features', blank=True, null=True)
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)



class Zanders(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    available = models.CharField(max_length=10, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    desc1 = models.TextField(blank=True, null=True)
    desc2 = models.TextField(blank=True, null=True)
    itemnumber = models.CharField(unique=True, max_length=255, blank=True, null=True)
    manufacturer = models.CharField(max_length=255, blank=True, null=True)
    mfgpnumber = models.CharField(max_length=255, blank=True, null=True)
    msrp = models.CharField(max_length=10, blank=True, null=True)
    price1 = models.CharField(max_length=10, blank=True, null=True)
    price2 = models.CharField(max_length=10, blank=True, null=True)
    price3 = models.CharField(max_length=10, blank=True, null=True)
    qty1 = models.CharField(max_length=10, blank=True, null=True)
    qty2 = models.CharField(max_length=10, blank=True, null=True)
    qty3 = models.CharField(max_length=10, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    weight = models.CharField(max_length=10, blank=True, null=True)
    serialized = models.CharField(max_length=10, blank=True, null=True)
    mapprice = models.CharField(max_length=10, blank=True, null=True)
    imagelink = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)
    active = models.BooleanField(default=False)
    total_product_cost = models.TextField(null=True)
