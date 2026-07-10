from kater.web import dashboard as _dashboard
from kater.web.review_fixes import apply_review_fixes

apply_review_fixes(_dashboard)
render_dashboard = _dashboard.render_dashboard

__all__ = ["render_dashboard"]
