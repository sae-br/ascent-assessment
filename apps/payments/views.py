from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def checkout(request):
    return render(request, 'payments/checkout.html')

@login_required
def success(request):
    return render(request, 'payments/success.html')