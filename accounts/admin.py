from django.contrib import admin
from .models import Candidate , Question , Answer

# Register your models here.
admin.site.register(Candidate)
admin.site.register(Question)
admin.site.register(Answer)