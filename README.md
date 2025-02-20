ASP Classic to ASP.NET Core MVC Migration Tool

📌 Overview:

This project automates the migration of ASP Classic projects to ASP.NET Core MVC using OpenAI API endpoints. 
The tool takes a GitHub repository URL as input, processes the ASP Classic code, and outputs a converted project as a downloadable ZIP file. 
The migration ensures proper project structuring, entity extraction, and adherence to best practices in ASP.NET Core


🔧 Technologies Used:

-Backend:
FastAPI (Python) for API development
OpenAI API for code transformation
GitHub API for repo access
MySQL (if needed for entity extraction)

-Frontend:
React (Vite) for UI
Tailwind CSS for styling


🎯 How It Works:

Enter GitHub Repo URL → The backend fetches and analyzes the ASP Classic project.
Extract and Convert → The tool extracts database info, converts legacy code, and structures the new project.
Generate Output → The final ASP.NET Core MVC project is structured and packaged.
Download ZIP → The user receives a converted project.
