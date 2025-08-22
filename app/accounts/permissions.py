from rest_framework.permissions import BasePermission

class CanCreateSubaccount(BasePermission):
    message = 'You have reached your subaccount limit or are not allowed to create subaccounts.'

    def has_permission(self, request, view):
        user = request.user

        if user.is_subaccount:
            self.message = 'Subaccounts are not allowed to create other subaccounts.'
            return False

        if not user.tier:
            self.message = 'No subscription tier assigned. Please upgrade your account.'
            return False

        if not user.can_create_subaccount:
            self.message = f'You have reached the maximum of {user.tier.max_subaccounts} subaccounts for your tier.'
            return False

        return True
