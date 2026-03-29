from supabase_client import supabase
from datetime import datetime

def increment_automation_execution_count(automation_id: str):
    # Get current execution_count
    response = supabase.table("automations").select("execution_count").eq("automation_id", automation_id).execute()
    
    if not response.data or len(response.data) == 0:
        print("Automation not found")
        return None

    current_count = response.data[0]["execution_count"]

    # Update execution_count and last_triggered_at
    res = supabase.table("automations").update(
        {
            "execution_count": current_count + 1,
            "last_triggered_at": datetime.utcnow().isoformat()  # UTC timestamp
        }
    ).eq("automation_id", automation_id).execute()

    if res:
        print("Incremented the automation execution count and updated last_triggered_at")
        return res
