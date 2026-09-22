"""Domain logic shared by the API routers.

Scaling and shopping-list generation both need the same rules -- work out an
effective scale, apply it to ingredient quantities, normalize units, merge what
can be merged. Those rules live here so an endpoint, a future import path and
eventually Agent Zero all call one implementation rather than three that drift.
"""
