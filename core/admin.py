from django.contrib import admin
from .models import User, Store, Category, DefectType, Product, Reservation


admin.site.site_header = 'Администрирование: УценкаМаркет'
admin.site.site_title = 'УценкаМаркет'
admin.site.index_title = 'Панель управления'



# Простая регистрация
admin.site.register(User)
admin.site.register(Store)
admin.site.register(Category)
admin.site.register(DefectType)
admin.site.register(Product)
admin.site.register(Reservation)