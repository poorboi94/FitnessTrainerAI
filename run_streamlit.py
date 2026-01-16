
#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

def main():
    print("Fitness Coach Agent - Streamlit")
    print("=" * 50)
    
    print("\nInstalling dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print("Dependencies installed!")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies")
        sys.exit(1)
    
    env_file = Path(".env")
    if not env_file.exists():
        print("\n No .env file found!")
        print("Creating .env template...")
        with open(".env", "w") as f:
            f.write("# Add your Groq API key here\n")
            f.write("GROQ_API_KEY=your_api_key_here\n")
        print(".env file created.")
        print("\nAdd your Groq API key to .env file and run again.")
        print("Get free API key at: https://console.groq.com")
        sys.exit(0)
    
    print("\n💾 Initializing database...")
    try:
        from app.database import init_db
        init_db()
        print("Database initialized!")
    except Exception as e:
        print(f"️Database: {e}")
    
    print("\nStarting Streamlit app...")
    print("=" * 50)
    print("\nOpen your browser to: http://localhost:8501")
    print("Press Ctrl+C to stop\n")
    
    try:
        subprocess.run(
            ["streamlit", "run", "streamlit_app.py"],
            check=True
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except subprocess.CalledProcessError:
        print("\nFailed to start Streamlit")
        print("Make sure Streamlit is installed: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main()