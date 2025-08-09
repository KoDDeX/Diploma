from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from .models import AutoServicePageVisit, AutoService


class AutoServiceVisitTrackingMiddleware(MiddlewareMixin):
    """
    Middleware для отслеживания посещений страниц автосервисов
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Отслеживаем посещения только на страницах автосервисов
        """
        try:
            # Определяем, является ли это страницей автосервиса
            url_name = resolve(request.path_info).url_name
            
            # Отслеживаем только детальную страницу автосервиса
            if url_name == 'autoservice_detail' and 'autoservice_slug' in view_kwargs:
                autoservice_slug = view_kwargs['autoservice_slug']
                
                try:
                    # Находим автосервис по slug
                    autoservice = AutoService.objects.get(slug=autoservice_slug, is_active=True)
                    
                    # Отслеживаем посещение
                    AutoServicePageVisit.track_visit(request, autoservice)
                    
                except AutoService.DoesNotExist:
                    # Автосервис не найден, ничего не делаем
                    pass
                    
        except Exception as e:
            # В случае любой ошибки просто продолжаем без отслеживания
            # Логирование можно добавить позже
            pass
        
        return None
