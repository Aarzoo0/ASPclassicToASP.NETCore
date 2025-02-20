import React, { useState } from "react";

const App = () => {
  const [githubUrl, setGithubUrl] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [zipFileUrl, setZipFileUrl] = useState(null);
  const [projectName, setProjectName] = useState("");

  // Extract the project name from the GitHub URL
  const extractProjectName = (url) => {
    const regex = /github\.com\/([^/]+)\/([^/]+)/;
    const match = url.match(regex);
    if (match) {
      return match[2]; // The second capture group is the repo name
    }
    return "project"; // Default name if URL is invalid
  };

  const handleMigration = async () => {
    if (!githubUrl) {
      alert("Please provide a GitHub repository URL.");
      return;
    }

    setIsProcessing(true);

    // Extract project name
    const name = extractProjectName(githubUrl);
    setProjectName(name);

    try {
      const response = await fetch("http://localhost:8000/process-github", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ githubUrl }),
      });

      if (!response.ok) {
        throw new Error("Error during migration.");
      }

      const data = await response.blob();
      const fileUrl = window.URL.createObjectURL(data);
      setZipFileUrl(fileUrl);
    } catch (error) {
      console.error(error);
      alert("An error occurred during the migration.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-10 rounded-xl shadow-2xl w-full max-w-lg">
        <h6 className="text-2xl font-bold text-center mb-6 text-gray-600 font-poppins">
          ASP Classic to ASP.NET Core MVC Migration Tool
        </h6>

        <div className="mb-6">
          <label
            htmlFor="githubUrl"
            className="block text-sm font-medium text-gray-700"
          >
            Enter GitHub Repository URL:
          </label>
          <input
            id="githubUrl"
            type="url"
            className="mt-3 p-4 w-full border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2d9d92] transition-all"
            placeholder="Enter GitHub URL"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
        </div>

        <div className="flex justify-center mb-6">
          <button
            onClick={handleMigration}
            disabled={isProcessing}
            className="bg-[#2d9d92] text-white font-semibold py-3 px-6 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2d9d92] hover:bg-[#269b85] hover:text-gray-700 transition-all duration-300 ease-in-out disabled:bg-grey-400"
          >
            {isProcessing ? "Processing..." : "Start Migration"}
          </button>
        </div>

        {/* Show success message after migration */}
        {zipFileUrl && !isProcessing && (
          <div className="mb-6 text-center text-gray-700">
            <p>Migration was successful! You can download the ZIP file now.</p>
          </div>
        )}

        {/* Show download button if migration is successful */}
        {zipFileUrl && (
          <div className="flex justify-center mb-6">
            <a
              href={zipFileUrl}
              download={`${projectName}_migration.zip`} // Set the download file name here
              className="bg-[#2d9d92] text-white font-semibold py-3 px-6 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2d9d92] hover:bg-[#269b85]  hover:text-gray-700 transition-all duration-300 ease-in-out"
            >
              Download ZIP File
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
