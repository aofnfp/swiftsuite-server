from rest_framework.pagination import LimitOffsetPagination
from rest_framework.exceptions import ParseError
from rest_framework.request import Request
from rest_framework.response import Response


class CustomOffsetPagination(LimitOffsetPagination):
    default_limit = 20
    
    def get_offset(self, request: Request, limit:int):
        try:
            page = int(request.query_params.get("page", 1))  
            if page < 1:
                raise ValueError("Page number must be greater than 0.")
            if limit < 1:
                raise ValueError("Limit must be greater than 0.")
            
        except ValueError as e:
            raise ParseError(str(e))
        
        return (page - 1) * limit
    
    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        try:
            limit = int(request.query_params.get("limit", self.default_limit))
        except ValueError:
            limit = self.default_limit
        
        offset = self.get_offset(request, limit)
        self.count = len(queryset) if isinstance(queryset, list) else queryset.count()
        self.offset = offset
        self.limit = limit
        
        if offset > self.count:
            return []

        return list(queryset[offset:offset + limit])
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.count,
            'results': data
            })

# from rest_framework.pagination import PageNumberPagination

# class CataloguePagination(PageNumberPagination):
#     page_size = 20  
#     page_size_query_param = 'page_size'
#     max_page_size = 1000
