from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import viewsets
from .models import Enrollment, Account, FragrancexUpdate, CwrUpdate, ZandersUpdate, LipseyUpdate, RsrUpdate, Generalproducttable, BackgroundTask
from vendorActivities.utils import VendorActivity, get_suppliers_for_vendor
from .serializers import (
    EnrollmentSerializer, 
    VendorTestSerializer, 
    AccountSerializer,
    LipseyUpdateSerializer,
    CwrUpdateSerializer,
    FragrancexUpdateSerializer,
    RsrUpdateSerializer,
    ZandersUpdateSerializer,
    GeneralProductSerializer,
    AccountWithEnrollmentsSerializer
    )
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .tasks import update_func, update_vendor_data
from rest_framework.decorators import api_view, permission_classes
from swiftsuite.vendorActivities.models import Vendors,Fragrancex, Lipsey, Cwr, Rsr, Ssi, Zanders
from rest_framework.generics import ListAPIView
from .pagination import CustomOffsetPagination
from swiftsuite.accounts.models import User
from .utils import map_vendor_data_to_general, identifier_filter
from django.db.models import Q


# Create your views here.
MODELS_MAPPING = {
        'fragrancex': Fragrancex,
        'cwr': Cwr,
        'lipsey': Lipsey,
        'ssi': Ssi,
        'zanders': Zanders,
        'rsr': Rsr
    }

UPDATE_MODELS_MAPPING = {
        'fragrancex': FragrancexUpdate,
        'cwr': CwrUpdate,
        'lipsey': LipseyUpdate,
        # 'ssi': Ssi,
        'zanders': ZandersUpdate,
        'rsr': RsrUpdate
    }

SERIALIZER_MAPPING = {
        'fragrancex': FragrancexUpdateSerializer,
        'cwr': CwrUpdateSerializer,
        'lipsey': LipseyUpdateSerializer,
        # 'ssi': Ssi,
        'zanders': ZandersUpdateSerializer,
        'rsr': RsrUpdateSerializer
    }

class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer
    
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        enrollment_id = response.data.get('id')
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
        BackgroundTask.objects.create(enrollment=enrollment) 
        update_vendor_data(enrollment)
        return response
    
class VendorTestView(APIView):
    def post(self, request):
        serializer = VendorTestSerializer(data = request.data)
        if serializer.is_valid():
            payload = serializer.validated_data
            vendor_name = Vendors.objects.get(id = payload['vendor'].id).name
            
            pull = VendorActivity()
            pull.justTest = True
            
            if vendor_name == 'fragrancex':
                apiAccessId = payload.get('apiAccessId')
                apiAccessKey = payload.get('apiAccessKey')
                supplier = (vendor_name, apiAccessId, apiAccessKey)
                process_vendor = pull.main(supplier)
            
            elif vendor_name == 'rsr':
                username = payload.get('Username')
                password = payload.get('Password')
                pos = payload.get('POS')
                supplier = ('rsr', username, password, pos)
                process_vendor = pull.main(supplier)
                
            else:
                ftp_host = payload.get('host')
                ftp_user = payload.get('ftp_username')
                ftp_password = payload.get('ftp_password')
                suppliers = get_suppliers_for_vendor(vendor_name, ftp_host, ftp_user, ftp_password)
                process_vendor = pull.main(suppliers)
            
            pull.removeFile()
            if not process_vendor and vendor_name != 'cwr':
                return Response({'error': f'Error processing {vendor_name}'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response(process_vendor, status= status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)       
        
class AccountViewset(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Account.objects.filter(user=user)

        vendor_id = self.request.query_params.get("vendor_id")
        if vendor_id:
            queryset = queryset.filter(vendor_id=vendor_id)

        return queryset
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "You do not have permission to delete this account."}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response({"message": "Account, Vendor data and enrollments deleted successfully."},status=status.HTTP_200_OK)

    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_enrolment(request, identifier):
    enrollment = get_object_or_404(Enrollment, user_id=request.user.id, identifier=identifier)
    serializer = EnrollmentSerializer(enrollment, data=request.data)
    if serializer.is_valid():
        serializer.save()
        # Start the update process in a separate thread
        updated_enrollment = serializer.instance
        update_vendor_data(updated_enrollment)
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_enrolment(request, identifier):
    enrolment = get_object_or_404(Enrollment, user_id=request.user.id, identifier=identifier)
    enrolment.delete()
    
    return Response({"message":"Enrollment Deleted Successfully"}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getEnrollmentWithIdentifier(request, identifier):
    enrollment = get_object_or_404(Enrollment, user_id=request.user.id, identifier=identifier)
    serializer = EnrollmentSerializer(enrollment)
    
    vendor_name = enrollment.vendor.name.lower()
    vendor_model = MODELS_MAPPING.get(vendor_name)
    enrollment = vendor_model.objects.all()
    
    # Process data based on vendor name
    response_data = {'enrollment': serializer.data}
    if vendor_name == 'rsr':
        product_category = (
            enrollment.values_list('category_name', flat=True)
            .distinct()
        )
        manufacturer = (
            enrollment.values_list('manufacturer_name', flat=True)
            .distinct()
        )
        shippable = (
            enrollment.values_list('drop_shippable', flat=True)
            .distinct()
        )
        
        response_data['product_category'] = list(product_category)
        response_data['manufacturer'] = list(manufacturer)
        response_data['shippable'] = list(shippable)
        
    elif vendor_name == 'fragrancex':
        brand = (
            enrollment.values_list('brandName', flat=True)
            .distinct()
        )
        response_data['brand'] = list(brand)
        
    elif vendor_name == 'lipsey':
        product_filter = (
            enrollment.values_list('itemtype', flat=True)
            .distinct()
        )
        
        manufacturer = (
            enrollment.values_list('manufacturer', flat=True)
            .distinct()
        )
        
        response_data['product_filter'] = list(product_filter)
        response_data['manufacturer'] = list(manufacturer)
        
    elif vendor_name == 'zanders':
        manufacturer = (
            enrollment.values_list('manufacturer', flat=True)
            .distinct()
        )
        response_data['manufacturer'] = list(manufacturer)
    
    elif vendor_name == 'ssi':
        product_category = (
            enrollment.values_list('category', flat=True)
            .distinct()
        )
        
        response_data['product_category'] = list(product_category)
    # Return the response
    return JsonResponse(response_data, status=status.HTTP_200_OK)

class CatalogueBaseView(ListAPIView):
    permission_classes = [IsAuthenticated]
    model = None 
    updateModel = None
    vendor_name = ''
    pagination_class = CustomOffsetPagination 

    def get_queryset(self):
        userid = self.request.user.id
        identifier = self.kwargs.get('identifier', None)
        return identifier_filter(Enrollment, self.vendor_name, identifier, userid, self.model, self.updateModel)   
        
    def get_serializer_class(self):
        if self.vendor_name == 'FragranceX':
            return FragrancexUpdateSerializer
        elif self.vendor_name == 'Zanders':
            return ZandersUpdateSerializer
        elif self.vendor_name == 'Lipsey':
            return LipseyUpdateSerializer
        elif self.vendor_name == 'RSR':
            return RsrUpdateSerializer
        elif self.vendor_name == 'CWR':
            return CwrUpdateSerializer
        # elif self.vendor_name == 'SSI':
        #     return SsiUpdateSerializer
        return None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset() 
        params = self.request.query_params
        filters = Q()
        search = params.get('search')
        minQty = params.get('minquantity')
        maxQty = params.get('maxquantity')
        minprice = params.get('minprice')
        maxprice = params.get('maxprice')
        
        
        if search:
            filters &= Q(product__upc__icontains=search) | Q(product__sku__icontains=search)  
        if minQty:
            filters &= Q(quantity__gte=minQty)
        if maxQty:
            filters &= Q(quantity__lte=maxQty)
        if minprice:   
            filters &= Q(price__gte=minprice)
        if maxprice:
            filters &= Q(price__lte=maxprice)
        
        if filters:
            queryset = queryset.filter(filters)
        
        if not queryset.exists():
            return Response({"message": "No data found"}, status=status.HTTP_404_NOT_FOUND)

        user_id = request.user.id
        # Get all vendor enrollments for this user and vendor
        enrollments = Enrollment.objects.filter(user_id=user_id, vendor__name=self.vendor_name).values("identifier")

        all_identifiers = [
            {"id": index + 1, "vendor_identifier": item["identifier"]}
            for index, item in enumerate(enrollments)
        ]
        page = self.paginate_queryset(queryset) 
        serializer_class = self.get_serializer_class()

        if page is not None:
            serializer = serializer_class(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data).data 
            paginated_response["all_identifiers"] = all_identifiers 
            return Response(paginated_response)

        serializer = serializer_class(queryset, many=True)
        return Response({"results": serializer.data, "all_identifiers": all_identifiers})
    
class CatalogueFragrancexView(CatalogueBaseView):
    model = Fragrancex
    vendor_name = 'FragranceX'
    updateModel = FragrancexUpdate
class CatalogueZandersView(CatalogueBaseView):
    model = Zanders
    vendor_name = 'Zanders'
    updateModel = ZandersUpdate
class CatalogueLipseyView(CatalogueBaseView):
    model = Lipsey
    vendor_name = 'Lipsey'
    updateModel = LipseyUpdate
class CatalogueSsiView(CatalogueBaseView):
    model = Ssi
    vendor_name = 'SSI'   
class CatalogueCwrView(CatalogueBaseView):
    model = Cwr
    vendor_name = 'CWR'
    updateModel = CwrUpdate  
class CatalogueRsrView(CatalogueBaseView):
    model = Rsr
    vendor_name = 'RSR'
    updateModel = RsrUpdate

class AllCatalogueView(ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomOffsetPagination

    def list(self, request, *args, **kwargs):
        user_id = request.user.id

        vendors = Enrollment.objects.filter(user_id=user_id).values_list('vendor__name', flat=True)
        vendors = {vendor.lower() for vendor in vendors}

        if not vendors:
            return Response({"message": "No data found"}, status=status.HTTP_404_NOT_FOUND)

        all_serialized = []
        for model_name, model_class in UPDATE_MODELS_MAPPING.items():
            if model_name in vendors:
                queryset = identifier_filter(Enrollment, model_name, None, user_id, model_class, model_class)
                serializer_class = SERIALIZER_MAPPING.get(model_name)
                if serializer_class:
                    serializer = serializer_class(queryset, many=True)
                    all_serialized.extend(serializer.data)

        if not all_serialized:
            return Response({"message": "No data found"}, status=status.HTTP_404_NOT_FOUND)

        # Paginate manually since we’re using a list
        page = self.paginate_queryset(all_serialized)
        if page is not None:
            return self.get_paginated_response(page)

        return Response({"results": all_serialized})

class AddProductView(APIView):
    # permission_classes = [IsAuthenticated]
    def get(self, request, userid, product_id, vendor_name, identifier = None):
        vendor_name = vendor_name.lower()

        if vendor_name not in UPDATE_MODELS_MAPPING:
            return JsonResponse({'error': 'Invalid vendor name'}, status=400)

        VENDOR_UPDATE = UPDATE_MODELS_MAPPING[vendor_name]

        product = VENDOR_UPDATE.objects.filter(product__id=product_id, account__user_id=userid).first()
        if not product:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        
        general_product_data = map_vendor_data_to_general(vendor_name, product, userid)

        return JsonResponse(general_product_data, status=status.HTTP_200_OK)

    def put(self, request, userid, product_id, vendor_name, identifier):
        vendor_name = vendor_name.lower()

        if vendor_name not in UPDATE_MODELS_MAPPING:
            return JsonResponse({'error': 'Invalid vendor name'}, status=400)
        
        VENDOR_UPDATE = UPDATE_MODELS_MAPPING[vendor_name]
        product = VENDOR_UPDATE.objects.filter(product__id=product_id, account__user_id=userid).first()
        if not product:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        product.active = True
        product.save()
        
        user = get_object_or_404(User, id=userid)
        general_product_data = map_vendor_data_to_general(vendor_name, product, user)

        enrollment = get_object_or_404(Enrollment, identifier=identifier, user_id=userid)

        general_product, created = Generalproducttable.objects.get_or_create(
            user=user,
            sku=general_product_data['sku'],
            enrollment= enrollment,
            product_id = product.product.id,
            defaults=general_product_data
        )

        if not created:
            # Update the existing record with new data
            for key, value in general_product_data.items():
                setattr(general_product, key, value)
            general_product.save()

        merged_data = {**general_product_data, **request.data}
        merged_data.pop('user', None)
        serializer = GeneralProductSerializer(general_product, data=merged_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def removeProduct(request, productId):
    try:
        # Try to fetch the product
        product = Generalproducttable.objects.get(id=productId, user=request.user.id)

        # Extract data BEFORE deletion
        product_id = product.product_id
        vendor_name = product.enrollment.vendor.name
        

        # Look up the correct update model
        product_model = UPDATE_MODELS_MAPPING.get(vendor_name.lower())
        if not product_model:
            return JsonResponse({'message': f'Unsupported vendor: {vendor_name}'}, status=400)

        # Mark vendor product as inactive
        try:
            updated_count = product_model.objects.filter(
                product__id=product_id,
                account__user=request.user
            ).update(active=False)
            
            # Delete the general product AFTER marking vendor updates inactive
            product.delete()
            
        except updated_count == 0:
            return JsonResponse({'message': 'Associated vendor product not found'}, status=404)

        return JsonResponse({'message': 'Product deleted successfully'})

    except Generalproducttable.DoesNotExist:
        return JsonResponse({'message': 'Product not found'}, status=404)

    except Exception as e:
        return JsonResponse({'message': str(e)}, status=500)

    
class ViewAllProducts(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GeneralProductSerializer
    pagination_class  = CustomOffsetPagination
    

    def get_queryset(self):
        user = self.request.user
        queryset = Generalproducttable.objects.filter(user=user, active=False).order_by('-date_created')
        params = self.request.query_params
        filters = Q()
        search = params.get('search')
        minQty = params.get('minquantity')
        maxQty = params.get('maxquantity')
        minprice = params.get('minprice')
        maxprice = params.get('maxprice')
        
        if search:
            filters &= Q(upc__icontains=search) | Q(sku__icontains=search)  
        if minQty:
            filters &= Q(quantity__gte=minQty)
        if maxQty:
            filters &= Q(quantity__lte=maxQty)
        if minprice:   
            filters &= Q(price__gte=minprice)
        if maxprice:
            filters &= Q(price__lte=maxprice)
        
        if filters:
            queryset = queryset.filter(filters)
        
        return queryset
        
class UserAccountEnrollmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        accounts = Account.objects.filter(user=user).select_related('vendor').prefetch_related('enrollments')
        data = AccountWithEnrollmentsSerializer(accounts, many=True).data
        return Response(data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def allEnrolledVendors(request):
    user = request.user
    vendors = Enrollment.objects.filter(user=user).values_list('vendor__name', flat=True).distinct()
    return Response({"vendors": list(vendors)}, status=status.HTTP_200_OK)