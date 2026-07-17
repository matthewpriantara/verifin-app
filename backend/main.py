from app.main import app

if __name__ == "__main__":
    import uvicorn
    # Run the modular application from the app package
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
