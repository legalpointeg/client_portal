class UploadsRouter:
    """يوجّه موديلات تطبيق uploads فقط إلى قاعدة بيانات uploads_db القديمة."""
    route_app_labels = {"uploads"}

    def db_for_read(self, model, **hints):
        return "uploads_db" if model._meta.app_label in self.route_app_labels else None

    def db_for_write(self, model, **hints):
        return "uploads_db" if model._meta.app_label in self.route_app_labels else None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == "uploads_db"
        return None
