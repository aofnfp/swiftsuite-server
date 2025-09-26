from rest_framework.permissions import BasePermission, SAFE_METHODS

class CanCreateSubaccount(BasePermission):
    message = 'You have reached your subaccount limit or are not allowed to create subaccounts.'

    def has_permission(self, request, view):
        user = request.user

        if user.is_subaccount:
            self.message = 'Subaccounts are not allowed to create other subaccounts.'
            return False
        
        if not user.subscribed:
            self.message = 'You need an active subscription to create subaccounts.'
            return False

        if not user.can_add_subaccount:
            self.message = 'You have reached your subaccount limit or are not allowed to create subaccounts.'
            return False
        
        return True

class IsOwnerOrHasPermission(BasePermission):
    """
    - Owners (parent accounts) can do everything if subscribed.
    - Subaccounts need explicit module permissions.
    """
    message = "You don't have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user

        # -------------------------
        # 1. Parent account (owner)
        # -------------------------
        if not user.is_subaccount:
            if not user.subscribed:
                self.message = "Your subscription is inactive. Please renew to access this feature."
                return False
            return True 

        # -------------------------
        # 2. Subaccount
        # -------------------------
        if not user.parent or not user.parent.subscribed:
            self.message = "Your parent account subscription is inactive."
            return False

        # -------------------------
        # 3. Module-specific check
        # -------------------------
        module_name = getattr(view, "module_name", None)
        if not module_name:
            self.message = "Module not specified for this view."
            return False

        permission = user.permissions.filter(module__name__iexact=module_name).first()
        if not permission:
            self.message = f"You don't have permissions for the {module_name} module."
            return False

        # -------------------------
        # 4. Method-based permission
        # -------------------------
        if request.method in SAFE_METHODS:
            if not permission.can_view:
                self.message = "You don't have view permission."
                return False

        elif request.method in ['PUT', 'PATCH', 'POST']:
            if not permission.can_edit:
                self.message = "You don't have edit permission."
                return False

        elif request.method == 'DELETE':
            if not permission.can_delete:
                self.message = "You don't have delete permission."
                return False

        else:
            self.message = "This action is not allowed for subaccounts."
            return False

        return True