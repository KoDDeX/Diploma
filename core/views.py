from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.

class LandingPageView(TemplateView):
    """Представление для главной страницы сайта."""
    template_name = 'core/landing.html'
    extra_context = {
        'title': '24автосервис',
        'description': '24автосервис - решение для автомобилей и их водителей на все случаи жизни!',
        # 'features': [
        #     'Expert Mechanics',
        #     'Affordable Prices',
        #     'Quick Service',
        #     'Customer Satisfaction Guaranteed'
        # ]
    }