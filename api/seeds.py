import requests
import json
import time
from datetime import datetime

API_BASE = "http://192.168.7.3:4000/api"

def wait_for_api():
    """Wait for API to be ready"""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://192.168.7.3:4000/healthz", timeout=5)
            if response.status_code == 200:
                print("✅ API is ready!")
                return True
        except:
            print(f"⏳ Waiting for API... (attempt {attempt + 1}/{max_attempts})")
            time.sleep(2)
    
    print("❌ API not ready after waiting")
    return False

def seed_sample_data():
    print("🌱 Seeding sprint data...")
    
    if not wait_for_api():
        return
    
    try:
        # Create a sprint
        sprint_data = {
            "name": "Sprint 1 - MVP Features",
            "goal": "Complete core user authentication and dashboard features",
            "duration_weeks": 2
        }
        
        print("📅 Creating sprint...")
        response = requests.post(f"{API_BASE}/sprints", json=sprint_data)
        if response.status_code == 200:
            sprint = response.json()
            sprint_id = sprint["id"]
            print(f"✅ Created sprint: {sprint['name']}")
            
            # Create sample issues
            issues_data = [
                {
                    "title": "User Login System",
                    "description": "Implement user authentication with email/password login functionality",
                    "issue_type": "STORY",
                    "priority": "HIGH",
                    "story_points": 8,
                    "assignee": "John Doe"
                },
                {
                    "title": "Dashboard Layout Design",
                    "description": "Create responsive main dashboard with navigation sidebar and content area",
                    "issue_type": "STORY", 
                    "priority": "MEDIUM",
                    "story_points": 5,
                    "assignee": "Jane Smith"
                },
                {
                    "title": "Fix login button alignment",
                    "description": "Login button appears misaligned on mobile devices below 768px width",
                    "issue_type": "BUG",
                    "priority": "LOW",
                    "story_points": 2,
                    "assignee": "Bob Wilson"
                },
                {
                    "title": "Setup CI/CD Pipeline",
                    "description": "Configure GitHub Actions for automated testing and deployment",
                    "issue_type": "TASK",
                    "priority": "MEDIUM",
                    "story_points": 3,
                    "assignee": "Alice Johnson"
                },
                {
                    "title": "User Profile Management",
                    "description": "Allow users to update profile information, avatar, and preferences",
                    "issue_type": "STORY",
                    "priority": "MEDIUM",
                    "story_points": 5,
                    "assignee": "John Doe"
                },
                {
                    "title": "Database Performance Optimization",
                    "description": "Optimize slow queries in user authentication and profile loading",
                    "issue_type": "TASK",
                    "priority": "HIGH",
                    "story_points": 8,
                    "assignee": "Jane Smith"
                },
                {
                    "title": "Password Reset Feature",
                    "description": "Implement forgot password functionality with email verification",
                    "issue_type": "STORY",
                    "priority": "MEDIUM",
                    "story_points": 3
                },
                {
                    "title": "Memory leak in dashboard",
                    "description": "Dashboard component causes memory usage to increase over time",
                    "issue_type": "BUG",
                    "priority": "CRITICAL",
                    "story_points": 5,
                    "assignee": "Alice Johnson"
                }
            ]
            
            print("📝 Creating issues...")
            created_issues = []
            for issue_data in issues_data:
                response = requests.post(f"{API_BASE}/issues", json=issue_data)
                if response.status_code == 200:
                    issue = response.json()
                    created_issues.append(issue)
                    print(f"✅ Created issue: {issue['key']} - {issue['title']}")
            
            # Add first 6 issues to sprint and set different statuses
            print("🚀 Organizing sprint...")
            if created_issues:
                statuses = ["TODO", "TODO", "IN_PROGRESS", "IN_PROGRESS", "DONE", "DONE"]
                
                for i, issue in enumerate(created_issues[:6]):
                    status = statuses[i] if i < len(statuses) else "TODO"
                    update_data = {
                        "sprint_id": sprint_id,
                        "status": status
                    }
                    
                    response = requests.put(f"{API_BASE}/issues/{issue['id']}", json=update_data)
                    if response.status_code == 200:
                        print(f"✅ Updated {issue['key']} - Status: {status}")
                
                # Start the sprint
                response = requests.put(f"{API_BASE}/sprints/{sprint_id}/start")
                if response.status_code == 200:
                    print(f"🏁 Started sprint: {sprint['name']}")
            
            # Create a second planned sprint
            sprint_2_data = {
                "name": "Sprint 2 - Advanced Features",
                "goal": "Implement reporting and advanced user features",
                "duration_weeks": 2
            }
            
            response = requests.post(f"{API_BASE}/sprints", json=sprint_2_data)
            if response.status_code == 200:
                sprint_2 = response.json()
                print(f"✅ Created second sprint: {sprint_2['name']}")
            
            print("\n" + "="*60)
            print("🎉 Sample data seeded successfully!")
            print("="*60)
            print("📱 Access your applications:")
            print("   • Main Dashboard: http://192.168.7.3:3000")
            print("   • Sprint Board:   http://192.168.7.3:3000/board")
            print("   • Backlog:        http://192.168.7.3:3000/backlog")
            print("   • API Docs:       http://192.168.7.3:4000/docs")
            print("="*60)
            
        else:
            print(f"❌ Failed to create sprint: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Make sure the API service is running.")
        print("   Try: docker-compose logs api")
    except Exception as e:
        print(f"❌ Error seeding data: {str(e)}")

def run():
    seed_sample_data()

if __name__ == "__main__":
    run()