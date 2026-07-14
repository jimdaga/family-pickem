from django.shortcuts import render

from pickem_superadmin.decorators import superadmin_required


@superadmin_required
def overview(request):
    return render(request, 'superadmin/overview.html', {})
