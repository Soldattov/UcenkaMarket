from django.urls import path

from . import views

app_name = 'core'

# В моделях Product и Reservation первичный ключ — UUID, поэтому здесь <uuid:id>.
# Если переведёте модели на целочисленный PK, замените на <int:id>.

urlpatterns = [
    path('', views.index, name='index'),
    path('logout/', views.logout, name='logout'),
    path('catalog/', views.catalog, name='catalog'),
    path('product/<uuid:id>/', views.product_detail, name='product_detail'),
    path('product/<uuid:id>/reserve/', views.reserve, name='reserve'),
    path('buyer/cabinet/', views.buyer_cabinet, name='buyer_cabinet'),
    path('manager/cabinet/', views.manager_cabinet, name='manager_cabinet'),
    path(
        'manager/reservation/<uuid:id>/complete/',
        views.complete_reservation,
        name='complete_reservation',
    ),
    path('seller/add/', views.seller_add, name='seller_add'),
    path(
        'api/address-suggest/',
        views.address_suggest,
        name='address_suggest',
    ),
    #тест
    path('api/debug/', views.api_debug, name='api_debug'),
]
