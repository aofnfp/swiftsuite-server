from django.db import models

# Create your models here.

class Vendors(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True, unique=True)
    logo = models.ImageField(upload_to='logos/')
    address_street1 = models.CharField(max_length=150, null=False)
    address_street2 = models.CharField(max_length=150, null=True)
    city = models.CharField(max_length=50, null=False)
    state = models.CharField(max_length=50, null=False)
    zip_code = models.CharField(max_length=50, null=False)
    country = models.CharField(max_length=50, null=False)
    has_data = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
        

# Individual Vendors products model

class Cwr(models.Model):
    id = models.BigAutoField(primary_key=True)
    cwr_part_number = models.TextField(blank=True, null=True)
    manufacturer_part_number = models.TextField(blank=True, null=True)
    upc = models.TextField(blank=True, null=True)
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
    uppercase_title = models.TextField(db_column='Uppercase Title', blank=True, null=True)  
    title = models.TextField(db_column='Title', blank=True, null=True)  # Field name made lowercase.
    full_description = models.TextField(db_column='Full Description', blank=True, null=True)  
    category_id = models.TextField(blank=True, null=True)
    category_name = models.TextField(db_column='Category Name', blank=True, null=True)  
    manufacturer_name = models.TextField(blank=True, null=True)  
    shipping_weight = models.TextField(blank=True, null=True)
    box_height = models.TextField(blank=True, null=True)
    box_length = models.TextField(blank=True, null=True)
    box_width = models.TextField(blank=True, null=True)
    list_of_accessories_by_sku = models.TextField(db_column='List of Accessories by SKU', blank=True, null=True)  
    list_of_accessories_by_mfg = models.TextField(db_column='List of Accessories by MFG#', blank=True, null=True)  
    quick_specs = models.TextField(db_column='Quick Specs', blank=True, null=True)  
    image_300x300_url = models.TextField(db_column='Image (300x300) Url', blank=True, null=True)  
    image_1000x1000_url = models.TextField(db_column='Image (1000x1000) Url', blank=True, null=True)  
    non_stock = models.TextField(blank=True, null=True)
    drop_ships_direct_from_vendor = models.TextField(blank=True, null=True)
    hazardous_materials = models.TextField(blank=True, null=True)
    truck_freight = models.BooleanField(blank=True, null=True)
    exportable = models.TextField(blank=True, null=True)
    first_class_mail = models.TextField(blank=True, null=True)
    oversized = models.BooleanField(blank=True, null=True)
    remanufactured = models.TextField(blank=True, null=True)
    closeout = models.TextField(blank=True, null=True)
    harmonization_code = models.TextField( blank=True, null=True)  
    country_of_origin = models.TextField( blank=True, null=True)  
    sale = models.TextField(blank=True, null=True)
    original_price_if_on_sale_closeout = models.TextField(blank=True, null=True)
    sale_start_date = models.TextField(blank=True, null=True)  
    sale_end_date = models.TextField(blank=True, null=True)  
    rebate = models.TextField(db_column='Rebate', blank=True, null=True)  
    rebate_description = models.TextField(db_column='Rebate Description', blank=True, null=True)  
    rebate_start_date = models.TextField(blank=True, null=True)  
    rebate_end_date = models.TextField(blank=True, null=True)  
    google_merchant_category = models.TextField(blank=True, null=True)  
    quick_guide_literature_pdf_url = models.TextField(blank=True, null=True)  
    owners_manual_pdf_url = models.TextField(blank=True, null=True)  
    brochure_literature_pdf_url = models.TextField(blank=True, null=True)  
    installation_guide_pdf_url = models.TextField(blank=True, null=True)  
    video_urls = models.TextField(db_column='Video Urls', blank=True, null=True)  
    prop_65 = models.TextField(blank=True, null=True)
    prop_65_description = models.TextField(db_column='Prop 65 Description', blank=True, null=True)  
    free_shipping = models.TextField(blank=True, null=True)
    free_shipping_end_date = models.TextField(db_column='Free Shipping End Date', blank=True, null=True)  
    returnable = models.BooleanField(blank=True, null=True)
    image_additional_1000x1000_urls = models.TextField(db_column='Image Additional (1000x1000) Urls', blank=True, null=True)  
    case_qty_nj = models.TextField(blank=True, null=True)
    case_qty_fl = models.TextField(blank=True, null=True)
    number_3rd_party_marketplaces = models.BooleanField(db_column='3rd Party Marketplaces', blank=True, null=True)
    fcc_id = models.TextField(db_column='FCC ID', blank=True, null=True)  
    sku = models.TextField(blank=True, null=True)
    mfgn = models.TextField(blank=True, null=True)
    qty = models.TextField(blank=True, null=True)
    qtynj = models.TextField(blank=True, null=True)
    qtyfl = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    map = models.TextField(blank=True, null=True)
    mrp = models.TextField(blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)

    
class Fragrancex(models.Model):
    sku = models.CharField(db_column='SKU', max_length=255, blank=True, null=True)  
    productName = models.CharField(db_column='PRODUCT_NAME', max_length=255, blank=True, null=True)  
    description = models.TextField(db_column='DESCRIPTION', blank=True, null=True)  
    brandName = models.CharField(db_column='BRAND_NAME', max_length=255, blank=True, null=True)  
    gender = models.CharField(db_column='GENDER', max_length=255, blank=True, null=True) 
    size = models.CharField(db_column='SIZE', max_length=255, blank=True, null=True)  
    metric_size = models.CharField(db_column='METRIC_SIZE', max_length=255, blank=True, null=True)  
    retailPriceUSD = models.CharField(db_column='RETAIL_PRICE_USD', max_length=255, blank=True, null=True)  
    wholesalePriceUSD = models.DecimalField(db_column='WHOLESALE_PRICE_USD', max_digits=10, decimal_places=2, blank=True, null=True)  
    wholesalePriceEUR = models.CharField(db_column='WHOLESALE_PRICE_EUR', max_length=255, blank=True, null=True)  
    wholesalePriceGBP = models.CharField(db_column='WHOLESALE_PRICE_GBP', max_length=255, blank=True, null=True)  
    wholesalePriceCAD = models.CharField(db_column='WHOLESALE_PRICE_CAD', max_length=255, blank=True, null=True)  
    wholesalePriceAUD = models.CharField(db_column='WHOLESALE_PRICE_AUD', max_length=255, blank=True, null=True)  
    smallImageUrl = models.CharField(db_column='SMALL_IMAGE_URL', max_length=255, blank=True, null=True)  
    largeImageUrl = models.CharField(db_column='LARGE_IMAGE_URL', max_length=255, blank=True, null=True)  
    type = models.CharField(db_column='TYPE', max_length=255, blank=True, null=True)  
    quantityAvailable = models.CharField(db_column='QUANTITY_AVAILABLE', max_length=255, blank=True, null=True)  
    upc = models.CharField(db_column='UPC', max_length=255, blank=True, null=True)  
    instock = models.CharField(db_column='INSTOCK', max_length=255, blank=True, null=True)  
    parentCode = models.CharField(db_column='PARENT_CODE', max_length=255, blank=True, null=True)  
    features = models.TextField(db_column='Features', blank=True, null=True)
    
class Lipsey(models.Model):
    sku = models.TextField(db_column='Sku', blank=True, null=True)
    description1 = models.TextField(db_column='Description1', blank=True, null=True)
    description2 = models.TextField(db_column='Description2', blank=True, null=True)
    upc = models.TextField(db_column='Upc', blank=True, null=True)
    manufacturermodelno = models.TextField(db_column='ManufacturerModelNo', blank=True, null=True)
    msrp = models.TextField(db_column='Msrp', blank=True, null=True)
    model = models.TextField(db_column='Model', blank=True, null=True)
    calibergauge = models.TextField(db_column='CaliberGauge', blank=True, null=True)
    manufacturer = models.TextField(db_column='Manufacturer', blank=True, null=True)
    type = models.TextField(db_column='Type', blank=True, null=True)
    action = models.TextField(db_column='Action', blank=True, null=True)
    barrellength = models.TextField(db_column='BarrelLength', blank=True, null=True)
    capacity = models.TextField(db_column='Capacity', blank=True, null=True)
    finish = models.TextField(db_column='Finish', blank=True, null=True)
    overalllength = models.TextField(db_column='OverallLength', blank=True, null=True)
    receiver = models.TextField(db_column='Receiver', blank=True, null=True)
    safety = models.TextField(db_column='Safety', blank=True, null=True)
    sights = models.TextField(db_column='Sights', blank=True, null=True)
    stockframegrips = models.TextField(db_column='StockFrameGrips', blank=True, null=True)
    magazine = models.TextField(db_column='Magazine', blank=True, null=True)
    weight = models.TextField(db_column='Weight', blank=True, null=True)
    imagename = models.TextField(db_column='ImageName', blank=True, null=True)
    chamber = models.TextField(db_column='Chamber', blank=True, null=True)
    drilledandtapped = models.TextField(db_column='DrilledAndTapped', blank=True, null=True)
    rateoftwist = models.TextField(db_column='RateOfTwist', blank=True, null=True)
    itemtype = models.TextField(db_column='ItemType', blank=True, null=True)
    additionalfeature1 = models.TextField(db_column='AdditionalFeature1', blank=True, null=True)
    additionalfeature2 = models.TextField(db_column='AdditionalFeature2', blank=True, null=True)
    additionalfeature3 = models.TextField(db_column='AdditionalFeature3', blank=True, null=True)
    shippingweight = models.TextField(db_column='ShippingWeight', blank=True, null=True)
    boundbookmanufacturer = models.TextField(db_column='BoundBookManufacturer', blank=True, null=True)
    boundbookmodel = models.TextField(db_column='BoundBookModel', blank=True, null=True)
    boundbooktype = models.TextField(db_column='BoundBookType', blank=True, null=True)
    nfathreadpattern = models.TextField(db_column='NfaThreadPattern', blank=True, null=True)
    nfaattachmentmethod = models.TextField(db_column='NfaAttachmentMethod', blank=True, null=True)
    nfabaffletype = models.TextField(db_column='NfaBaffleType', blank=True, null=True)
    silencercanbedisassembled = models.TextField(db_column='SilencerCanBeDisassembled', blank=True, null=True)
    silencerconstructionmaterial = models.TextField(db_column='SilencerConstructionMaterial', blank=True, null=True)
    nfadbreduction = models.TextField(db_column='NfaDbReduction', blank=True, null=True)
    silenceroutsidediameter = models.TextField(db_column='SilencerOutsideDiameter', blank=True, null=True)
    nfaform3caliber = models.TextField(db_column='NfaForm3Caliber', blank=True, null=True)
    opticmagnification = models.TextField(db_column='OpticMagnification', blank=True, null=True)
    maintubesize = models.TextField(db_column='MaintubeSize', blank=True, null=True)
    adjustableobjective = models.TextField(db_column='AdjustableObjective', blank=True, null=True)
    objectivesize = models.TextField(db_column='ObjectiveSize', blank=True, null=True)
    opticadjustments = models.TextField(db_column='OpticAdjustments', blank=True, null=True)
    illuminatedreticle = models.TextField(db_column='IlluminatedReticle', blank=True, null=True)
    reticle = models.TextField(db_column='Reticle', blank=True, null=True)
    exclusive = models.TextField(db_column='Exclusive', blank=True, null=True)
    quantity = models.PositiveIntegerField(db_column='Quantity', blank=True, null=True)
    allocated = models.TextField(db_column='Allocated', blank=True, null=True)
    onsale = models.TextField(db_column='OnSale', blank=True, null=True)
    price = models.DecimalField(db_column='Price', max_digits=10, decimal_places=2, blank=True, null=True)
    currentprice = models.TextField(db_column='CurrentPrice', blank=True, null=True)
    retailmap = models.TextField(db_column='RetailMap', blank=True, null=True)
    fflrequired = models.TextField(db_column='FflRequired', blank=True, null=True)
    sotrequired = models.TextField(db_column='SotRequired', blank=True, null=True)
    exclusivetype = models.TextField(db_column='ExclusiveType', blank=True, null=True)
    scopecoverincluded = models.TextField(db_column='ScopeCoverIncluded', blank=True, null=True)
    special = models.TextField(db_column='Special', blank=True, null=True)
    sightstype = models.TextField(db_column='SightsType', blank=True, null=True)
    case = models.TextField(db_column='Case', blank=True, null=True)
    choke = models.TextField(db_column='Choke', blank=True, null=True)
    dbreduction = models.TextField(db_column='DbReduction', blank=True, null=True)
    family = models.TextField(db_column='Family', blank=True, null=True)
    finishtype = models.TextField(db_column='FinishType', blank=True, null=True)
    frame = models.TextField(db_column='Frame', blank=True, null=True)
    griptype = models.TextField(db_column='GripType', blank=True, null=True)
    handgunslidematerial = models.TextField(db_column='HandgunSlideMaterial', blank=True, null=True)
    countryoforigin = models.TextField(db_column='CountryOfOrigin', blank=True, null=True)
    itemlength = models.TextField(db_column='ItemLength', blank=True, null=True)
    itemwidth = models.TextField(db_column='ItemWidth', blank=True, null=True)
    itemheight = models.TextField(db_column='ItemHeight', blank=True, null=True)
    packagelength = models.TextField(db_column='PackageLength', blank=True, null=True)
    packagewidth = models.TextField(db_column='PackageWidth', blank=True, null=True)
    packageheight = models.TextField(db_column='PackageHeight', blank=True, null=True)
    itemgroup = models.TextField(db_column='ItemGroup', blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)

class Rsr(models.Model):
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
    map = models.DecimalField(max_digits=10, decimal_places=2, db_column='MAP', blank=True, null=True)  # RetailMAP
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
    images = models.TextField(null=True)


class Ssi(models.Model):
    sku = models.CharField(db_column='SKU', max_length=255, blank=True, null=True, db_index=True)
    description = models.CharField(db_column='Description', max_length=255, blank=True, null=True)
    datecreated = models.CharField(db_column='DateCreated', max_length=255, blank=True, null=True)
    dimensionh = models.CharField(db_column='DimensionH', max_length=255, blank=True, null=True)
    dimensionl = models.CharField(db_column='DimensionL', max_length=255, blank=True, null=True)
    dimensionw = models.CharField(db_column='DimensionW', max_length=255, blank=True, null=True)
    manufacturer = models.CharField(db_column='Manufacturer', max_length=255, blank=True, null=True)
    imageurl = models.CharField(db_column='ImageURL', max_length=255, blank=True, null=True)
    thumbnailurl = models.CharField(db_column='ThumbnailURL', max_length=255, blank=True, null=True)
    upccode = models.CharField(db_column='UPCCode', max_length=255, blank=True, null=True, db_index=True)
    weight = models.CharField(db_column='Weight', max_length=255, blank=True, null=True)
    weightunits = models.CharField(db_column='WeightUnits', max_length=255, blank=True, null=True)
    category = models.CharField(db_column='Category', max_length=255, blank=True, null=True, db_index=True)
    subcategory = models.CharField(db_column='Subcategory', max_length=255, blank=True, null=True)
    status = models.CharField(db_column='Status', max_length=255, blank=True, null=True)
    map = models.CharField(db_column='MAP', max_length=255, blank=True, null=True)
    msrp = models.CharField(db_column='MSRP', max_length=255, blank=True, null=True)
    mpn = models.CharField(db_column='MPN', max_length=255, blank=True, null=True)
    minimumorderquantity = models.CharField(db_column='MinimumOrderQuantity', max_length=255, blank=True, null=True)
    detaileddescription = models.TextField(db_column='DetailedDescription', blank=True, null=True)
    shippingweight = models.CharField(db_column='ShippingWeight', max_length=255, blank=True, null=True)
    shippinglength = models.CharField(db_column='ShippingLength', max_length=255, blank=True, null=True)
    shippingwidth = models.CharField(db_column='ShippingWidth', max_length=255, blank=True, null=True)
    shippingheight = models.CharField(db_column='ShippingHeight', max_length=255, blank=True, null=True)
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
    price = models.CharField(db_column='Price', max_length=255, blank=True, null=True)
    avgshipcost = models.TextField(blank=True, null=True)
    qty = models.CharField(db_column='Qty', max_length=255, blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)

class Zanders(models.Model):
    available = models.CharField(max_length=10, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    desc1 = models.TextField(blank=True, null=True)
    desc2 = models.TextField(blank=True, null=True)
    sku = models.CharField(unique=True, max_length=255, blank=True, null=True)
    manufacturer = models.CharField(max_length=255, blank=True, null=True)
    mfgpnumber = models.CharField(max_length=255, blank=True, null=True)
    msrp = models.CharField(max_length=10, blank=True, null=True)
    price1 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    price2 = models.CharField(max_length=10, blank=True, null=True)
    price3 = models.CharField(max_length=10, blank=True, null=True)
    qty1 = models.CharField(max_length=10, blank=True, null=True)
    qty2 = models.CharField(max_length=10, blank=True, null=True)
    qty3 = models.CharField(max_length=10, blank=True, null=True)
    upc = models.CharField(max_length=255, blank=True, null=True)
    weight = models.CharField(max_length=10, blank=True, null=True)
    serialized = models.CharField(max_length=10, blank=True, null=True)
    map = models.CharField(max_length=10, blank=True, null=True)
    imagelink = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    features = models.TextField(db_column='Features', blank=True, null=True)