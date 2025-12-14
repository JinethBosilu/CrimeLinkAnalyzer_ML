from datetime import datetime
from typing import List, Dict, Any, Optional

def _parse_dt(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts = ts.strip().replace(" ", "T")
    try:
        return datetime.fromisoformat(ts)
    except:
        return None

def compute_location_periods(call_records: List[Dict[str, Any]], gap_minutes: int = 30) -> Dict[str, Any]:
    """
    Timeline-based sessions:
    - Sort by time
    - Split when location changes OR gap > gap_minutes
    Output is ordered sessions (so you will see Urubokka2 -> Matara -> Urubokka2 -> Matara ...)
    """

    # Build timeline points
    points = []
    for r in call_records:
        loc = r.get("location") or r.get("call_name")
        dt = _parse_dt(r.get("timestamp"))
        if loc and dt:
            points.append((dt, loc))

    # If nothing parsed, return empty
    if not points:
        return {"gap_minutes": gap_minutes, "locations": []}

    # Sort by time
    points.sort(key=lambda x: x[0])

    sessions = []
    start_dt = points[0][0]
    end_dt = points[0][0]
    current_loc = points[0][1]
    count = 1

    for dt, loc in points[1:]:
        gap = (dt - end_dt).total_seconds() / 60.0

        # Split if location changes OR gap is large
        if loc != current_loc or gap > gap_minutes:
            sessions.append({
                "location": current_loc,
                "start": start_dt.strftime("%H:%M"),
                "end": end_dt.strftime("%H:%M"),
                "count": count,
            })
            # start new
            start_dt = dt
            end_dt = dt
            current_loc = loc
            count = 1
        else:
            end_dt = dt
            count += 1

    # last session
    sessions.append({
        "location": current_loc,
        "start": start_dt.strftime("%H:%M"),
        "end": end_dt.strftime("%H:%M"),
        "count": count,
    })

    return {"gap_minutes": gap_minutes, "locations": sessions}
