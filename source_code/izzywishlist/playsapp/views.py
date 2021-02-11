from django.shortcuts import render
from django.views import View


class PSView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'playsapp/index.html', context={})
