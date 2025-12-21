from accounts.tasks import send_normal_email as send_email

class BaseNotificationSender:
    def __init__(self, notification_obj):
        self.notification = notification_obj

    def send(self):
        raise NotImplementedError("Subclasses must implement send()")

class EmailNotificationSender(BaseNotificationSender):
    def send(self):
        # TODO: Implement actual email sending logic
        context = {
            'user': self.notification.recipient_user.id,
            'email_subject': self.notification.template.header,
            'body': self.notification.template.body,
        }
        send_email.delay(context, file='notification.html')

class PushNotificationSender(BaseNotificationSender):
    def send(self):
        pass

class InAppNotificationSender(BaseNotificationSender):
    def send(self):
        pass

class InAppBannerSender(BaseNotificationSender):
    def send(self):
        pass



SENDER_REGISTRY = {
    "email": EmailNotificationSender,
    "push": PushNotificationSender,
    "in_app": InAppNotificationSender,
    "in_app_banner": InAppBannerSender,
}

