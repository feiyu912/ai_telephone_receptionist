"""Business hours check based on tenant configuration."""

from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.schemas import TenantConfig


def is_within_business_hours(tenant: TenantConfig) -> bool:
    """Check if current time is within tenant's business hours."""
    tz = ZoneInfo(tenant.business_hours_timezone)
    now = datetime.now(tz)

    # isoweekday(): Monday=1 ... Sunday=7
    if now.isoweekday() not in tenant.business_hours_days:
        return False

    return tenant.business_hours_start <= now.hour < tenant.business_hours_end
