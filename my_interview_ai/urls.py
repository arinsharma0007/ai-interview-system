"""
URL configuration for my_interview project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf.urls import handler400, handler403, handler404, handler500
from django.shortcuts import render




def error_400_view(request, exception):
    return render(request, 'errors/400.html', status=400)

def error_403_view(request, exception):
    return render(request, 'errors/403.html', status=403)

def error_404_view(request, exception):
    return render(request, 'errors/404.html', status=404)

def error_500_view(request):
    return render(request, 'errors/500.html', status=500)

handler400 = error_400_view
handler403 = error_403_view
handler404 = error_404_view
handler500 = error_500_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('' ,include('accounts.urls'))
    
]