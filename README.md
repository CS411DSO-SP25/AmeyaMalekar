# Title: Scholar Atlas

## Purpose
Scholar Atlas is a comprehensive web application designed to help academic researchers, university administrators, and research analysts track and analyze academic research output. The dashboard provides tools for managing faculty profiles, tracking publications, analyzing research networks, and comparing research metrics across universities.
The aim of this dashboard is to give users the ability to explore universities, faculty, and publications in a comprehensive manner.

### Target Users
- Academic researchers looking to track their publications and collaborations
- University administrators monitoring research output
- Research analysts studying academic trends and patterns
- Faculty members managing their research profiles

### Objectives
- Provide a centralized platform for academic research management
- Enable efficient tracking of publications and citations
- Visualize research networks and collaborations
- Analyze research trends and patterns
- Compare research output across institutions

## Demo Video
https://drive.google.com/file/d/1IXZ7d3hzy4ZAeKJo1Fpz7ewZP1aqDuEP/view?usp=drive_link

## Installation
1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file with the following variables:
```
MYSQL_HOST=your_mysql_host
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_mysql_database
MONGODB_URI=your_mongodb_uri
NEO4J_URI=your_neo4j_uri
NEO4J_USER=your_neo4j_user
NEO4J_PASSWORD=your_neo4j_password
```

5. Run the application:
```bash
python app.py
```

## Usage
1. Access the dashboard through your web browser at `http://localhost:8050`
2. Use the various widgets to:
   - View and manage faculty profiles
   - Submit and track publications
   - Search and analyze publications
   - Visualize research networks
   - Analyze keyword relationships
   - Compare university research output

## Design
The application follows a modular design with the following components:

### Architecture
- Frontend: Dash (Python web framework)
- Backend: Python
- Databases:
  - MySQL: Faculty and university data
  - MongoDB: Publication data
  - Neo4j: Research networks and keyword relationships

### Components
1. Faculty Summary Widget
2. Faculty Profile Management Widget
3. Publication Submission Widget
4. Publication Search Widget
5. Research Network Visualizer Widget
6. Keyword Analysis Widget
7. University Research Dashboard Widget

## Implementation
The application is implemented using the following technologies:

### Frameworks and Libraries
- Dash: Web framework for building the dashboard
- Plotly: Interactive data visualization
- NetworkX: Network analysis and visualization
- Pandas: Data manipulation and analysis
- MySQL Connector: MySQL database connectivity
- PyMongo: MongoDB database connectivity
- Neo4j Python Driver: Neo4j database connectivity

### Tools
- Python 3.x
- Virtual Environment
- Git for version control

## Widgets Overview and Requirements Met:

## 1. Faculty Profile Management Widget (Update Widget)
- **Purpose**: Allow users to add or update faculty information
- **Database**: MySQL
- **Functionality**:
  - Add new faculty members with their details (name, position, research interests, etc.)
  - Update existing faculty information
  - Link faculty to universities
  - Input validation and error handling
- **Requirements Met**: R10 (Updating widget)

## 2. Publication Submission Widget (Update Widget)
- **Purpose**: Enable users to add new publications to the system
- **Database**: MongoDB
- **Functionality**:
  - Submit new publications with metadata (title, venue, year, citations)
  - Associate publications with keywords
  - Link publications to authors
  - Bulk upload capability for multiple publications
- **Requirements Met**: R10 (Updating widget)

## 3. Publication Search Widget (Query Widget)
- **Purpose**: Search and analyze publications
- **Database**: MongoDB
- **Functionality**:
  - Search publications by title, keywords, or year
  - Filter by citation count
  - Sort by relevance or date
  - Display publication trends over time
- **Requirements Met**: R11 (Querying widget)

## 4. Research Network Visualizer Widget (Query Widget)
- **Purpose**: Visualize academic collaboration networks
- **Database**: Neo4j
- **Functionality**:
  - Display faculty collaboration networks
  - Show co-authorship relationships
  - Highlight research clusters
  - Interactive network exploration
- **Requirements Met**: R11 (Querying widget)

## 5. Keyword Analysis Widget (Query Widget)
- **Purpose**: Explore and visualize keyword relationships
- **Database**: Neo4j
- **Functionality**:
  - Display keyword co-occurrence graph
  - Search for a keyword to see related terms
  - Highlight top 10 most frequent keywords
  - Interactive graph with tooltips
- **Requirements Met**: R11 (Querying widget)

## 6. University Research Dashboard Widget (Query Widget)
- **Purpose**: Analyze research output by university
- **Database**: MySQL
- **Functionality**:
  - Dropdown to select and compare 2 universities
  - Show faculty count and total publications
  - Display average citations per publication
  - Simple bar chart for visual comparison
- **Requirements Met**: R11 (Querying widget)

## 7. Faculty Summary Widget (Query Widget)
- **Purpose**: Provide a snapshot of a faculty member’s research contributions
- **Database**: MySQL
- **Functionality**:
  - Input: Dropdown to select a faculty member
  - Show:
    - Number of publications
    - Affiliated university
    - Research interests
- **Requirements Met**: R11 (Querying widget)

## Database Techniques
The application implements several database techniques to optimize performance and functionality:

1. **Indexing**
   - Created an index for faculty searches:
   ```sql
   CREATE INDEX idx_faculty_university_interest ON Faculty(name(100), university_id, research_interest(100));
   ```

2. **Prepared Statements**
   - All widgets that accept user input utilize prepared statements
   - Input parameters are properly sanitized to prevent SQL injection

3. **Views**
   - Created a view called 'universitypublicationstats' for efficient querying (Widget 7)
   - ```sql
      CREATE VIEW UniversityPublicationStats AS
         SELECT 
            u.id AS university_id,
            u.name AS university_name,
            f.id AS faculty_id,
            f.name AS faculty_name,
            p.id AS publication_id,
            p.title AS publication_title,
            p.num_citations
         FROM university u
         JOIN faculty f ON u.id = f.university_id
         JOIN faculty_publication fp ON f.id = fp.faculty_id
         JOIN publication p ON fp.publication_id = p.id;
      ```
   - Reduces the need for repeated table joins

## Contributions
I worked alone to create this application.
