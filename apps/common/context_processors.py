# For breadcrumbs and associating pages with specific nav links

def current_section(request):
    path = request.path

    if path.startswith("/dashboard"):
        return {"section": "dashboard"}
    elif path.startswith("/assessments"):
        return {"section": "assessments"}
    elif path.startswith("/teams"):
        return {"section": "teams"}
    elif path.startswith("/reports"):
        return {"section": "reports"}
    elif path.startswith("/accounts"):
        return {"section": "account"}
    elif path.startswith("/payments") or path.startswith("/settings"):
        return {"section": "other"}
    else:
        return {"section": ""}