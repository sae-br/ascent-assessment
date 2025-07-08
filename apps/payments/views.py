from django.shortcuts import render

def checkout(request):
    return render(request, 'payments/checkout.html')

def success(request):
    return render(request, 'payments/success.html')