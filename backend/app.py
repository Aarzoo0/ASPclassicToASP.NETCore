import os
import zipfile
import json
import uuid
from dotenv import load_dotenv
import subprocess
import shutil
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io
import tempfile
import stat
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from concurrent.futures import ThreadPoolExecutor
import re
from pathlib import Path

# Load environment variables
load_dotenv()

# Azure OpenAI API configuration
api_base = os.getenv("AZURE_ENDPOINT").split("/openai")[0]
api_key = os.getenv("AZURE_API_KEY")
api_version = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")
deployment_name = "gpt-4o-001"

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Langchain with Azure OpenAI
llm = AzureChatOpenAI(
    openai_api_version=api_version,
    azure_deployment=deployment_name,
    azure_endpoint=api_base,
    api_key=api_key,
    temperature=0.7
)

# Create a chat prompt template for ASP Classic analysis
prompt_template = ChatPromptTemplate.from_messages([ 
    ("system", "You are an expert software engineer specialized in analyzing ASP Classic projects and classifying files for conversion to ASP.NET Core MVC."),
    ("user", "{input}")
])

# Create the chain
llm_chain = prompt_template | llm | StrOutputParser()

def clone_and_zip_repo(github_url):
    """
    Clones a GitHub repository, zips it, and returns the path to the zip file.
    """
    try:
        temp_clone_path = tempfile.mkdtemp()
        print(f"Cloning repository from {github_url} to {temp_clone_path}...")
        result = subprocess.run(
            ["git", "clone", github_url, temp_clone_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.returncode != 0:
            print(f"Git clone error: {result.stderr}")
            return None, None
        
        print(f"Repository cloned successfully.")
        
        zip_path = os.path.join(tempfile.gettempdir(), "cloned_repo.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_clone_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_clone_path)
                    zipf.write(file_path, arcname)
        
        print(f"Repository zipped successfully to {zip_path}.")
        return zip_path, temp_clone_path
    except Exception as e:
        print(f"Failed to clone and zip repository: {e}")
        return None, None

def handle_remove_readonly(func, path, exc_info):
    """
    Error handler for removing read-only files.
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)

def classify_file_with_openai(file_path, content):
    """
    Classifies an ASP Classic file using Azure OpenAI based on its content.
    """
    try:
        # Escape backslashes and double quotes properly
        safe_content = content.replace("\\", "\\\\").replace('"', '\\"')
        safe_file_path = file_path.replace("\\", "\\\\").replace('"', '\\"')

        # Format the JSON correctly within the prompt
        prompt = f"""
        ## **File Classification for ASP Classic to ASP.NET Core MVC Migration**
        **File Path:** {safe_file_path}
        **File Content:**
        ```
        {safe_content}
        ```
        ### **Classification Criteria:**
        1. **Files that need full conversion** → ASP pages (.asp), business logic, data access
        2. **Files that need minor modifications** → HTML templates, utility functions
        3. **Files that are not needed** → Deprecated features, old configurations

        ### **Return JSON Format:**
        ```json
        {json.dumps({
            "file_path": safe_file_path,
            "classification": "conversion_needed",
            "reason": "Detailed explanation of why this classification was chosen.",
            "category": "Views",
            "conversion_type": "Razor View"
        }, indent=2)}
        ```
        """
        print(f"Classifying file: {file_path}")
        response = llm_chain.invoke({"input": prompt})

        # Extract JSON from markdown block if necessary
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        return json.loads(response)  # Fallback
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return {
            "file_path": file_path,
            "classification": "unknown",
            "reason": f"JSON parsing error: {str(e)}",
            "category": "Other",
            "conversion_type": "Unknown"
        }

def analyze_asp_project(project_path):
    """
    Analyzes the ASP Classic project structure and classifies each file.
    """
    project_structure = {
        "Views": [],
        "Controllers": [],
        "Models": [],
        "Configurations": [],
        "Other": []
    }

    def analyze_file(file_path):
        content = read_file_content(file_path)
        if not content:
            return
        classification = classify_file_with_openai(file_path, content)
        category = classification.get("category", "Other")
        if category in project_structure:
            project_structure[category].append({
                "file_path": file_path,
                "classification": classification["classification"],
                "reason": classification["reason"],
                "conversion_type": classification.get("conversion_type", "Unknown"),
                "content": content
            })

    with ThreadPoolExecutor() as executor:
        futures = []
        for root, dirs, files in os.walk(project_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for file in files:
                if file.lower().endswith(('.asp', '.asa', '.inc', '.html', '.css', '.js')) :
                    file_path = os.path.join(root, file)
                    futures.append(executor.submit(analyze_file, file_path))
        
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Error processing file: {e}")

    return project_structure

def generate_mvc_with_openai(analysis_data, project_name):
    try:
        # Ensure JSON structure is properly escaped
        formatted_analysis_data = json.dumps(analysis_data, indent=2)

        # Generate a GUID for the project
        project_guid = str(uuid.uuid4())

        prompt = f"""
        ## **Complete ASP Classic to ASP.NET Core MVC Migration for {project_name}**
        ### **Analysis Data:**
        ```json
        {formatted_analysis_data}
        ```

        ### **Required Structure:**
        ``` 
        ├── Controllers/
        │   └── HomeController.cs
        ├── Models/
        │   └── [DomainModel].cs  # Each domain model should have its own file like UserEntity.cs, ProductEntity.cs
        ├── Views/
        │   ├── Shared/
        │   │   └── _Layout.cshtml
        │   └── Home/
        │       └── Index.cshtml
        ├── wwwroot/
        │   ├── css/
        │   │   └── [styles].css   # Ensure styles are included
        │   ├── js/
        │   │   └── [scripts].js   # Ensure JS files are added
        │   └── lib/
        ├── Data/
        │   └──ApplicationDbContext.cs
        ├── Services/
        │   └── Service.cs
        ├── Properties/
        │   └── launchSettings.json
        ├── appsettings.json
        ├── Program.cs
        ├── {project_name}Project.csproj
        └── {project_name}Solution.sln
        ```

        ### **Code Generation Instructions:**

        1. **Ensure Proper Database Setup:**
            - **In `Data/ApplicationDbContext.cs`:**
              - Create the `ApplicationDbContext` class and extend `DbContext`.
              - Ensure the `DbContext` is properly configured for Entity Framework Core.
              - If you're using SQL Server, reference `Microsoft.EntityFrameworkCore.SqlServer`.

        2. **Ensure Proper Controller and Service Naming Conventions:**
            - **In `Controllers/HomeController.cs`:**
              - Use the `HomeController` naming convention.
              - Implement the necessary actions to handle routing and views.

        3. **Model Generation:**
            - **In `Models/[DomainModel].cs`:**
              - For each domain model (e.g., `User`, `Product`, etc.), generate a corresponding `.cs` file like `UserEntity.cs` or `ProductEntity.cs`.
              - Ensure models are compatible with Entity Framework Core (e.g., `DbSet<T>`).
              - Define properties that match the fields found in the analysis data (e.g., `FirstName`, `LastName`, `Email`, etc.).
              - Initialize non-nullable properties or mark them as nullable.

        4. **View Generation:**
            - **In `Views/Home/Index.cshtml`:**
              - Generate the view for `HomeController.Index`.
              - Include necessary layout and views structure.
              - Ensure references to CSS and JS are included in the layout.

        5. **CSS and JS Files:**
            - **In `wwwroot/css/`:**
              - Ensure that CSS files are generated for styling purposes.
              - Add a sample `styles.css` file in the `wwwroot/css/` folder.
            - **In `wwwroot/js/`:**
              - Add JavaScript files for any front-end functionality. Create `scripts.js` or relevant files to handle interactions.

        6. **AppSettings and Configuration:**
            - **In `appsettings.json`:**
              - Add the connection string for the database.

        7. **Program.cs Setup:**
            - Configure `ApplicationDbContext` in the `Program.cs` for dependency injection.
            - Register required services like MVC and EF Core.
            - **Integrate Swagger** in the `Program.cs` to enable API documentation.
            - Using `Microsoft.AspNetCore.Builder;` and `Microsoft.Extensions.DependencyInjection;` as imports.

        8. **Ensure that the following files are correctly populated:**
            - `{project_name}Project.csproj`: Add references to `Microsoft.EntityFrameworkCore` and `Microsoft.EntityFrameworkCore.SqlServer`.
            - `launchSettings.json`: Configure appropriate environment settings for development.

        ### **Generated Code Example:**
        For each model in the analysis data, ensure that an entity class file is created in `Models/` like:

        - **`UserEntity.cs`:**
        ```csharp
        public class UserEntity
        {{
            public string? FirstName {{ get; set; }}
            public string? LastName {{ get; set; }}
            public string? Email {{ get; set; }}
            public string? Phone {{ get; set; }}
        }}
        ```

        - **`ProductEntity.cs`:**
        ```csharp
        public class ProductEntity
        {{
            public string? Name {{ get; set; }}
            public decimal? Price {{ get; set; }}
            public int? Stock {{ get; set; }}
        }}
        ```

        ### **Swagger Integration:**
        **In `Program.cs`:**
        - Add Swagger services and middleware to the pipeline to enable API documentation:

        ```csharp
        public class Program
        {{
            public static void Main(string[] args)
            {{
                var builder = WebApplication.CreateBuilder(args);

                // Add services to the container.
                builder.Services.AddControllersWithViews();
                builder.Services.AddDbContext<ApplicationDbContext>(options =>
                    options.UseSqlServer(builder.Configuration.GetConnectionString("DefaultConnection")));

                // Register Swagger for API documentation
                builder.Services.AddEndpointsApiExplorer();
                builder.Services.AddSwaggerGen();

                var app = builder.Build();

                // Configure the HTTP request pipeline.
                if (app.Environment.IsDevelopment())
                {{
                    app.UseDeveloperExceptionPage();
                    app.UseSwagger();  // Enable Swagger UI in Development
                    app.UseSwaggerUI();  // Swagger UI to visualize API docs
                }}
                else
                {{
                    app.UseExceptionHandler("/Home/Error");
                    app.UseHsts();
                }}

                app.UseHttpsRedirection();
                app.UseStaticFiles();

                app.UseRouting();

                app.UseAuthorization();

                app.MapControllerRoute(
                    name: "default",
                    pattern: "{{controller=Home}}/{{action=Index}}/{{id?}}");

                app.Run();
            }}
        }}
        ```

        ### **Fixing Model Issues:**
        - **In `UserEntity.cs`:**
            - Ensure that the properties are initialized in the constructor or marked as nullable if required.

        ```csharp
        public class UserEntity
        {{
            public string? FirstName {{ get; set; }}
            public string? LastName {{ get; set; }}
            public string? Email {{ get; set; }}
            public string? Phone {{ get; set; }}
        }}
        ```

        ### **Generated Code Example:**
        - **`ApplicationDbContext.cs`**
        ```csharp
        public class ApplicationDbContext : DbContext
        {{
            public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
                : base(options) {{ }}

            public DbSet<UserEntity> Users {{ get; set; }}
            public DbSet<ProductEntity> Products {{ get; set; }}
        }}
        ```

        - **`UserService.cs`**
        ```csharp
        public class UserService
        {{
            private readonly ApplicationDbContext _context;

            public UserService(ApplicationDbContext context)
            {{
                _context = context;
            }}

            public async Task<List<UserEntity>> GetUsersAsync()
            {{
                return await _context.Users.ToListAsync();
            }}
        }}
        ```

        ### **CSS and JS Example:**
        - **`wwwroot/css/styles.css`:**
        ```css
        body {{
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
        }}

        h1 {{
            color: #333;
        }}
        ```

        - **`wwwroot/js/scripts.js`:**
        ```javascript
        document.addEventListener("DOMContentLoaded", function() {{
            console.log("Page loaded!");
        }});
        ```

        Return a JSON object where:
        - Each key is a file path.
        - Each value is the full content of the file.
        """

        print(f"Generating MVC project files for {project_name} with analysis data.")
        response = llm_chain.invoke({"input": prompt})

        # Print the raw response for debugging
        print(f"Raw OpenAI Response: {response}")

        # Ensure response is valid JSON
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            content = json.loads(json_match.group(1))
            return content

        return json.loads(response)  # Fallback JSON parsing
    except json.JSONDecodeError:
        print("Error generating MVC project files")
        return {}


def read_file_content(file_path):
    """
    Reads the content of a file and returns it as a string.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except UnicodeDecodeError:
        try:
            # Try different encodings for ASP Classic files
            with open(file_path, "r", encoding="windows-1252") as file:
                return file.read()
        except:
            print(f"Skipping binary file: {file_path}")
            return None
    except Exception as e:
        print(f"Failed to read file {file_path}: {e}")
        return None

def save_zip_to_downloads(project_dir, zip_file_name):
    # Create a BytesIO buffer to hold the zip data
    zip_buffer = io.BytesIO()

    # Create a zip file in memory
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_dir)
                zipf.write(file_path, arcname)

    # Save the zip buffer to a file in the Downloads folder
    downloads_folder = str(Path.home() / "Downloads")
    zip_file_path = os.path.join(downloads_folder, zip_file_name)

    # Move the buffer's pointer to the beginning of the buffer
    zip_buffer.seek(0)

    # Write the buffer to the file
    with open(zip_file_path, 'wb') as f:
        f.write(zip_buffer.read())

    print(f"Project zipped successfully to {zip_file_path}")

@app.post("/process-github")
async def process_github(request: Request):
    data = await request.json()
    github_url = data.get("githubUrl")
    if not github_url:
        raise HTTPException(status_code=400, detail="GitHub URL is required")
    
    try:
        # Clone and analyze the repository
        zip_path, temp_clone_path = clone_and_zip_repo(github_url)
        if not zip_path:
            raise HTTPException(status_code=500, detail="Failed to clone repository")

        # Analyze the ASP Classic project
        asp_structure = analyze_asp_project(temp_clone_path)

        # Dynamically determine the project name (e.g., based on the GitHub repo name)
        project_name = github_url.split('/')[-1].replace('.git', '')

        # Generate MVC project
        mvc_content = generate_mvc_with_openai(asp_structure, project_name)
        
        # Create output directory structure
        output_dir = tempfile.mkdtemp()
        project_dir = os.path.join(output_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # Write MVC project files
        for relative_path, content in mvc_content.items():
            file_path = os.path.join(project_dir, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Convert dictionary to JSON string if content is a dictionary
            if isinstance(content, dict):
                content = json.dumps(content, indent=4)
            # Ensure content is string
            elif not isinstance(content, str):
                content = str(content)
                
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, project_dir)
                    zipf.write(file_path, arcname)

        # Optionally save to local Downloads folder
        save_zip_to_downloads(project_dir, f"{project_name}.zip")  # Save locally

        # Clean up
        if os.path.exists(temp_clone_path):
            shutil.rmtree(temp_clone_path, onerror=handle_remove_readonly)
        shutil.rmtree(output_dir, onerror=handle_remove_readonly)
        
        # Return zip file to the user
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={project_name}_mvc_project.zip"}
        )
    
    except Exception as e:
        print(f"Error processing GitHub URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
