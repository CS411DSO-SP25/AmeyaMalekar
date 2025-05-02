import dash
from dash import html, dash_table, dcc, Input, Output, State
import pandas as pd
from database.mysql_connection import get_mysql_connection
from database.mongodb_connection import get_mongodb_connection
from database.neo4j_connection import get_neo4j_connection
import os
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import io
import base64
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx

app = dash.Dash(__name__)

# Function to fetch faculty data from MySQL
def get_faculty_data():
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = "SELECT id, name, position, research_interest, email FROM faculty LIMIT 5"
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                df = pd.DataFrame(data, columns=columns)
                return df
        except Exception as e:
            print(f"Error executing MySQL query: {e}")
            return pd.DataFrame()
        finally:
            connection.close()
    return pd.DataFrame()

# Function to fetch publication data from MongoDB
def get_publication_data():
    try:
        print("\nAttempting to fetch publication data from MongoDB...")
        db = get_mongodb_connection()
        if db is not None:
            publications = list(db.publications.find(
                {},
                {
                    '_id': 1,
                    'id': 1,
                    'title': 1,
                    'venue': 1,
                    'year': 1,
                    'numCitations': 1,
                    'keywords': 1
                }
            ).limit(2))
            
            if publications:
                for pub in publications:
                    pub['_id'] = str(pub['_id'])
                    pub['keywords'] = ', '.join([k['name'] for k in pub.get('keywords', [])])
                df = pd.DataFrame(publications)
                return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error executing MongoDB query: {e}")
        return pd.DataFrame()

# Function to fetch data from Neo4j
def get_neo4j_data():
    try:
        driver = get_neo4j_connection()
        if driver is not None:
            with driver.session(database=os.getenv('NEO4J_DATABASE', 'academicworld')) as session:
                query = """
                MATCH (f:FACULTY)-[:PUBLISH]->(p:PUBLICATION)
                RETURN f.name as faculty_name,
                       f.position as position,
                       p.title as publication_title,
                       p.year as year
                LIMIT 5
                """
                result = session.run(query)
                records = [dict(record) for record in result]
                if records:
                    df = pd.DataFrame(records)
                    return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error executing Neo4j query: {e}")
        return pd.DataFrame()

# Function to get universities for dropdown
def get_universities():
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = "SELECT id, name FROM university"
                cursor.execute(query)
                return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching universities: {e}")
            return []
        finally:
            connection.close()
    return []

# Function to get existing faculty for publication author selection
def get_faculty_for_dropdown():
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = "SELECT id, name FROM faculty ORDER BY name"
                cursor.execute(query)
                return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching faculty: {e}")
            return []
        finally:
            connection.close()
    return []

# Function to get research interests data (simplified)
def get_research_interests():
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT f.research_interest, COUNT(*) as count
                FROM faculty f
                GROUP BY f.research_interest
                ORDER BY count DESC
                LIMIT 10
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching research interests: {e}")
            return []
        finally:
            connection.close()
    return []

# Function to create word cloud
def create_wordcloud(data):
    # Create a dictionary of research interests and their frequencies
    word_freq = {row[0]: row[1] for row in data}
    
    # Generate word cloud
    wordcloud = WordCloud(width=400, height=300, 
                         background_color='white',
                         colormap='viridis',
                         max_words=50).generate_from_frequencies(word_freq)
    
    # Convert to base64 for display
    plt.figure(figsize=(10, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    return f'data:image/png;base64,{img_base64}'

# Get the data
faculty_df = get_faculty_data()
publication_df = get_publication_data()
neo4j_df = get_neo4j_data()

# Function to get publication data from MongoDB
def get_publications(search_term=None, min_citations=None, year_range=None):
    try:
        db = get_mongodb_connection()
        if db is not None:
            query = {}
            
            # Add search term filter
            if search_term:
                query['$or'] = [
                    {'title': {'$regex': search_term, '$options': 'i'}},
                    {'keywords.name': {'$regex': search_term, '$options': 'i'}}
                ]
            
            # Add citation filter
            if min_citations:
                query['numCitations'] = {'$gte': min_citations}
            
            # Add year range filter
            if year_range:
                query['year'] = {'$gte': year_range[0], '$lte': year_range[1]}
            
            publications = list(db.publications.find(
                query,
                {
                    '_id': 1,
                    'title': 1,
                    'venue': 1,
                    'year': 1,
                    'numCitations': 1,
                    'keywords': 1
                }
            ).limit(100))
            
            if publications:
                for pub in publications:
                    pub['_id'] = str(pub['_id'])
                    pub['keywords'] = ', '.join([k['name'] for k in pub.get('keywords', [])])
                return publications
        return []
    except Exception as e:
        print(f"Error executing MongoDB query: {e}")
        return []

# Function to get collaboration network data from Neo4j
def get_collaboration_network(faculty_name=None):
    try:
        driver = get_neo4j_connection()
        if driver is not None:
            with driver.session(database=os.getenv('NEO4J_DATABASE', 'academicworld')) as session:
                if faculty_name:
                    query = """
                    MATCH (f1:FACULTY {name: $faculty_name})-[:PUBLISH]->(p:PUBLICATION)<-[:PUBLISH]-(f2:FACULTY)
                    WHERE f1 <> f2
                    RETURN f1.name as source, f2.name as target, count(p) as weight
                    ORDER BY weight DESC
                    LIMIT 20
                    """
                    result = session.run(query, faculty_name=faculty_name)
                else:
                    query = """
                    MATCH (f1:FACULTY)-[:PUBLISH]->(p:PUBLICATION)<-[:PUBLISH]-(f2:FACULTY)
                    WHERE f1 <> f2
                    WITH f1, f2, count(p) as weight
                    ORDER BY weight DESC
                    LIMIT 50
                    RETURN f1.name as source, f2.name as target, weight
                    """
                    result = session.run(query)
                
                records = [dict(record) for record in result]
                return records
        return []
    except Exception as e:
        print(f"Error executing Neo4j query: {e}")
        return []

# Function to get keyword relationships from Neo4j
def get_keyword_relationships(search_term=None):
    try:
        driver = get_neo4j_connection()
        if driver is not None:
            with driver.session(database=os.getenv('NEO4J_DATABASE', 'academicworld')) as session:
                # If search term is provided, get related keywords
                if search_term:
                    related_query = """
                    MATCH (k1:KEYWORD {name: $search_term})<-[:LABEL_BY]-(p:PUBLICATION)-[:LABEL_BY]->(k2:KEYWORD)
                    WHERE k1 <> k2
                    WITH k2.name as keyword, count(p) as frequency
                    ORDER BY frequency DESC
                    LIMIT 10
                    RETURN keyword, frequency
                    """
                    result = session.run(related_query, search_term=search_term)
                    related_keywords = [dict(record) for record in result]
                    
                    # Get co-occurrence relationships between the search term and related keywords
                    co_occurrence_query = """
                    MATCH (k1:KEYWORD {name: $search_term})<-[:LABEL_BY]-(p:PUBLICATION)-[:LABEL_BY]->(k2:KEYWORD)
                    WHERE k1 <> k2
                    WITH k1.name as source, k2.name as target, count(p) as weight
                    WHERE k2.name IN $related_keywords
                    RETURN source, target, weight
                    ORDER BY weight DESC
                    """
                    related_keyword_names = [record['keyword'] for record in related_keywords]
                    result = session.run(co_occurrence_query, search_term=search_term, related_keywords=related_keyword_names)
                    relationships = [dict(record) for record in result]
                    
                    # Also add relationships between related keywords
                    related_relationships_query = """
                    MATCH (k1:KEYWORD)<-[:LABEL_BY]-(p:PUBLICATION)-[:LABEL_BY]->(k2:KEYWORD)
                    WHERE k1.name IN $related_keywords AND k2.name IN $related_keywords AND k1.name < k2.name
                    WITH k1.name as source, k2.name as target, count(p) as weight
                    RETURN source, target, weight
                    ORDER BY weight DESC
                    LIMIT 20
                    """
                    result = session.run(related_relationships_query, related_keywords=related_keyword_names)
                    related_relationships = [dict(record) for record in result]
                    
                    # Combine direct relationships with related ones
                    all_relationships = relationships + related_relationships
                    
                    return {
                        'top_keywords': related_keywords,
                        'relationships': all_relationships,
                        'search_term': search_term
                    }
                # Otherwise, get top 10 most frequent keywords
                else:
                    query = """
                    MATCH (p:PUBLICATION)-[:LABEL_BY]->(k:KEYWORD)
                    WITH k.name as keyword, count(p) as frequency
                    ORDER BY frequency DESC
                    LIMIT 10
                    RETURN keyword, frequency
                    """
                    result = session.run(query)
                    top_keywords = [dict(record) for record in result]
                    
                    # Get co-occurrence relationships for the top keywords
                    co_occurrence_query = """
                    MATCH (p:PUBLICATION)-[:LABEL_BY]->(k1:KEYWORD)
                    MATCH (p)-[:LABEL_BY]->(k2:KEYWORD)
                    WHERE k1.name IN $keywords AND k2.name IN $keywords AND k1.name < k2.name
                    WITH k1.name as source, k2.name as target, count(p) as weight
                    RETURN source, target, weight
                    ORDER BY weight DESC
                    LIMIT 20
                    """
                    keywords = [record['keyword'] for record in top_keywords]
                    result = session.run(co_occurrence_query, keywords=keywords)
                    relationships = [dict(record) for record in result]
                    
                    return {
                        'top_keywords': top_keywords,
                        'relationships': relationships,
                        'search_term': None
                    }
        return {'top_keywords': [], 'relationships': [], 'search_term': None}
    except Exception as e:
        print(f"Error executing Neo4j query: {e}")
        return {'top_keywords': [], 'relationships': [], 'search_term': None}

# Function to get university research data from MySQL
def get_university_research_data(university_ids=None):
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                if university_ids:
                    # Get data for specific universities using the view
                    query = """
                    SELECT 
                        university_id,
                        university_name,
                        COUNT(DISTINCT faculty_id) as faculty_count,
                        COUNT(DISTINCT publication_id) as publication_count,
                        AVG(num_citations) as avg_citations
                    FROM UniversityPublicationStats
                    WHERE university_id = %s OR university_id = %s
                    GROUP BY university_id, university_name
                    """
                    cursor.execute(query, (university_ids[0], university_ids[1]))
                    result = cursor.fetchall()
                    
                    # Process results
                    universities = []
                    for row in result:
                        uni_id, name, faculty_count, pub_count, avg_citations = row
                        universities.append({
                            'id': uni_id,
                            'name': name,
                            'faculty_count': faculty_count,
                            'publication_count': pub_count,
                            'avg_citations': float(avg_citations) if avg_citations else 0
                        })
                    return universities
                else:
                    # Get all universities for dropdown
                    cursor.execute("SELECT id, name FROM university ORDER BY name")
                    return cursor.fetchall()
        except Exception as e:
            print(f"Error executing MySQL query: {e}")
        finally:
            connection.close()
    return []

# Function to get faculty summary data for Widget 8
def get_faculty_summary(faculty_id):
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Get faculty details including publication count and university
                query = """
                SELECT f.id, f.name, f.position, f.research_interest, f.email, 
                       u.name as university_name,
                       (SELECT COUNT(*) FROM faculty_publication fp WHERE fp.faculty_Id = f.id) as publication_count
                FROM faculty f
                LEFT JOIN university u ON f.university_id = u.id
                WHERE f.id = %s
                """
                cursor.execute(query, (faculty_id,))
                result = cursor.fetchone()
                
                if result:
                    # Convert to dictionary
                    columns = ['id', 'name', 'position', 'research_interest', 'email', 'university_name', 'publication_count']
                    faculty_data = dict(zip(columns, result))
                    
                    # Get research keywords for the faculty (top 5)
                    keywords_query = """
                    SELECT k.name, fk.score
                    FROM faculty_keyword fk
                    JOIN keyword k ON fk.keyword_id = k.id
                    WHERE fk.faculty_id = %s
                    ORDER BY fk.score DESC
                    LIMIT 5
                    """
                    cursor.execute(keywords_query, (faculty_id,))
                    faculty_data['keywords'] = [{'name': row[0], 'score': float(row[1])} for row in cursor.fetchall()]
                    
                    return faculty_data
                return None
        except Exception as e:
            print(f"Error getting faculty summary: {e}")
        finally:
            connection.close()
    return None

# Define the app layout
app.layout = html.Div([
    # Hidden div for callbacks
    html.Div(id='_', style={'display': 'none'}),
    
    html.Div([
        html.H1('Scholar Atlas', 
                style={'textAlign': 'center', 
                       'color': '#2c3e50',
                       'marginBottom': '30px',
                       'fontFamily': 'Arial, sans-serif'}),
        
        # Main content area with flex layout
        html.Div([
            # 1. Faculty Summary Widget (at top)
            html.Div([
                html.H2('Faculty Summary', 
                       style={'color': '#2c3e50',
                              'borderBottom': '2px solid #3498db',
                              'paddingBottom': '10px',
                              'marginBottom': '15px',
                              'fontSize': '1.2em'}),
                
                html.Div([
                    # Faculty selection
                    html.Div([
                        html.Label('Select Faculty Member', 
                                 style={'display': 'block',
                                        'marginBottom': '8px',
                                        'fontWeight': 'bold',
                                        'color': '#34495e',
                                        'fontSize': '0.9em'}),
                        dcc.Dropdown(
                            id='faculty-summary-dropdown',
                            options=[],  # Will be populated
                            placeholder='Select a faculty member',
                            style={'width': '100%'}
                        ),
                        html.Button('View Summary', 
                                  id='view-faculty-button',
                                  n_clicks=0,
                                  style={'backgroundColor': '#3498db',
                                         'color': 'white',
                                         'padding': '8px 16px',
                                         'border': 'none',
                                         'borderRadius': '4px',
                                         'cursor': 'pointer',
                                         'fontSize': '0.9em',
                                         'fontWeight': 'bold',
                                         'marginTop': '10px',
                                         'marginBottom': '20px'})
                    ], style={'marginBottom': '20px'}),
                    
                    # Faculty summary display
                    html.Div([
                        # Summary header
                        html.Div(id='faculty-summary-header',
                                children=[],
                                style={'textAlign': 'center',
                                       'marginBottom': '15px',
                                       'fontWeight': 'bold',
                                       'fontSize': '1.1em',
                                       'color': '#2c3e50'}),
                        
                        # Summary content
                        html.Div([
                            # Left column: Basic info
                            html.Div([
                                html.Div([
                                    html.Strong('Position: '),
                                    html.Span(id='faculty-position-display')
                                ], style={'marginBottom': '10px'}),
                                
                                html.Div([
                                    html.Strong('University: '),
                                    html.Span(id='faculty-university-display')
                                ], style={'marginBottom': '10px'}),
                                
                                html.Div([
                                    html.Strong('Email: '),
                                    html.Span(id='faculty-email-display')
                                ], style={'marginBottom': '10px'}),
                                
                                html.Div([
                                    html.Strong('Publications: '),
                                    html.Span(id='faculty-publications-display')
                                ], style={'marginBottom': '10px'})
                            ], style={'flex': '1', 'marginRight': '20px'}),
                            
                            # Right column: Research interests and keywords
                            html.Div([
                                html.Div([
                                    html.Strong('Research Interest: '),
                                    html.Div(id='faculty-interest-display',
                                           style={'marginTop': '5px',
                                                  'marginBottom': '15px'})
                                ]),
                                
                                html.Div([
                                    html.Strong('Top Keywords: '),
                                    html.Div(id='faculty-keywords-display',
                                           style={'marginTop': '10px'})
                                ])
                            ], style={'flex': '1'})
                        ], style={'display': 'flex', 'marginBottom': '20px'})
                    ], id='faculty-summary-content', style={'display': 'none'})
                ], style={'padding': '20px',
                          'backgroundColor': 'white',
                          'borderRadius': '8px',
                          'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ], style={'marginBottom': '30px'}),
            
            # 2. Publication Search Widget
            html.Div([
                html.H2('Publication Search', 
                       style={'color': '#2c3e50',
                              'borderBottom': '2px solid #3498db',
                              'paddingBottom': '10px',
                              'marginBottom': '15px',
                              'fontSize': '1.2em'}),
                
                html.Div([
                    # Search and filter controls
                    html.Div([
                        # Search input
                        html.Div([
                            html.Label('Search Publications', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-search', 
                                    type='text', 
                                    placeholder='Search by title or keywords...',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Filters row
                        html.Div([
                            # Min citations filter
                            html.Div([
                                html.Label('Minimum Citations', 
                                         style={'display': 'block',
                                                'marginBottom': '2px',
                                                'fontWeight': 'bold',
                                                'color': '#34495e',
                                                'fontSize': '0.9em'}),
                                dcc.Input(id='min-citations', 
                                        type='number', 
                                        placeholder='Min citations',
                                        min=0,
                                        style={'width': '100%',
                                               'padding': '8px',
                                               'borderRadius': '4px',
                                               'border': '1px solid #bdc3c7',
                                               'fontSize': '0.9em'})
                            ], style={'flex': '1',
                                     'marginRight': '20px'}),
                            
                            # Year range filter
                            html.Div([
                                html.Label('Year Range', 
                                         style={'display': 'block',
                                                'marginBottom': '2px',
                                                'fontWeight': 'bold',
                                                'color': '#34495e',
                                                'fontSize': '0.9em'}),
                                dcc.RangeSlider(
                                    id='year-range',
                                    min=1900,
                                    max=2024,
                                    step=1,
                                    value=[2000, 2024],
                                    marks={i: str(i) for i in range(1900, 2025, 10)},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], style={'flex': '2'})
                        ], style={'display': 'flex',
                                 'marginBottom': '20px'})
                    ]),
                    
                    # Publication table
                    html.Div([
                        dash_table.DataTable(
                            id='publication-table',
                            columns=[
                                {'name': 'Title', 'id': 'title'},
                                {'name': 'Venue', 'id': 'venue'},
                                {'name': 'Year', 'id': 'year'},
                                {'name': 'Citations', 'id': 'numCitations'},
                                {'name': 'Keywords', 'id': 'keywords'}
                            ],
                            style_table={'overflowX': 'auto'},
                            style_cell={
                                'textAlign': 'left',
                                'padding': '10px',
                                'whiteSpace': 'normal',
                                'height': 'auto'
                            },
                            style_header={
                                'backgroundColor': '#3498db',
                                'color': 'white',
                                'fontWeight': 'bold'
                            },
                            style_data_conditional=[
                                {
                                    'if': {'row_index': 'odd'},
                                    'backgroundColor': 'rgb(248, 248, 248)'
                                }
                            ],
                            page_size=10,
                            sort_action='native',
                            filter_action='native'
                        )
                    ], style={'backgroundColor': 'white',
                             'padding': '20px',
                             'borderRadius': '8px',
                             'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
                ], style={'padding': '20px',
                          'backgroundColor': 'white',
                          'borderRadius': '8px',
                          'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ], style={'marginBottom': '30px'}),
            
            # 3. Research Network Visualizer Widget
            html.Div([
                html.H2('Research Network Visualizer', 
                       style={'color': '#2c3e50',
                              'borderBottom': '2px solid #3498db',
                              'paddingBottom': '10px',
                              'marginBottom': '15px',
                              'fontSize': '1.2em'}),
                
                html.Div([
                    # Search and filter controls
                    html.Div([
                        # Faculty search
                        html.Div([
                            html.Label('Search Faculty', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-search', 
                                    type='text', 
                                    placeholder='Enter faculty name to view their network...',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Network controls
                        html.Div([
                            html.Label('Network Settings', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            html.Div([
                                # Node size control
                                html.Div([
                                    html.Label('Faculty Name Size', 
                                             style={'display': 'block',
                                                    'marginBottom': '2px',
                                                    'color': '#34495e',
                                                    'fontSize': '0.9em'}),
                                    html.Div('Adjust how large faculty names appear',
                                            style={'fontSize': '0.8em',
                                                   'color': '#7f8c8d',
                                                   'marginBottom': '5px'}),
                                    dcc.Slider(
                                        id='node-size',
                                        min=5,
                                        max=20,
                                        step=1,
                                        value=10,
                                        marks={i: str(i) for i in range(5, 21, 5)}
                                    )
                                ], style={'flex': '1',
                                         'marginRight': '20px'}),
                                
                                # Link strength control
                                html.Div([
                                    html.Label('Collaboration Line Thickness', 
                                             style={'display': 'block',
                                                    'marginBottom': '2px',
                                                    'color': '#34495e',
                                                    'fontSize': '0.9em'}),
                                    html.Div('Adjust how thick collaboration lines appear (thicker = more papers)',
                                            style={'fontSize': '0.8em',
                                                   'color': '#7f8c8d',
                                                   'marginBottom': '5px'}),
                                    dcc.Slider(
                                        id='link-strength',
                                        min=1,
                                        max=5,
                                        step=1,
                                        value=2,
                                        marks={i: str(i) for i in range(1, 6)}
                                    )
                                ], style={'flex': '1'})
                            ], style={'display': 'flex',
                                     'marginBottom': '20px'})
                        ])
                    ]),
                    
                    # Network visualization
                    html.Div([
                        dcc.Graph(id='network-graph',
                                style={'height': '500px'})
                    ], style={'backgroundColor': 'white',
                             'padding': '20px',
                             'borderRadius': '8px',
                             'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
                ], style={'padding': '20px',
                          'backgroundColor': 'white',
                          'borderRadius': '8px',
                          'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ], style={'marginBottom': '30px'}),
            
            # 4. Keyword Analysis Widget
            html.Div([
                html.H2('Keyword Analysis', 
                       style={'color': '#2c3e50',
                              'borderBottom': '2px solid #3498db',
                              'paddingBottom': '10px',
                              'marginBottom': '15px',
                              'fontSize': '1.2em'}),
                
                html.Div([
                    # Search box
                    html.Div([
                        html.Label('Search Keywords', 
                                 style={'display': 'block',
                                        'marginBottom': '2px',
                                        'fontWeight': 'bold',
                                        'color': '#34495e',
                                        'fontSize': '0.9em'}),
                        html.Div([
                            dcc.Input(id='keyword-search', 
                                    type='text', 
                                    placeholder='Enter a keyword to see related terms...',
                                    style={'width': '70%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'fontSize': '0.9em'}),
                            html.Button('Search', 
                                      id='keyword-search-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#3498db',
                                             'color': 'white',
                                             'padding': '8px 16px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '0.9em',
                                             'fontWeight': 'bold',
                                             'marginLeft': '10px'})
                        ], style={'display': 'flex',
                                 'alignItems': 'center',
                                 'marginBottom': '15px'})
                    ]),
                    
                    # Top Keywords Bar Chart
                    html.Div([
                        html.H3(id='keyword-chart-title',
                               children='Top 10 Keywords by Frequency',
                               style={'color': '#34495e',
                                      'marginBottom': '10px',
                                      'fontSize': '1.1em'}),
                        dcc.Graph(id='keyword-frequency-chart',
                                 style={'height': '300px'})
                    ], style={'backgroundColor': 'white',
                             'padding': '20px',
                             'borderRadius': '8px',
                             'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                             'marginBottom': '20px'}),
                    
                    # Keyword Co-occurrence Network
                    html.Div([
                        html.H3('Keyword Co-occurrence Network',
                               style={'color': '#34495e',
                                      'marginBottom': '10px',
                                      'fontSize': '1.1em'}),
                        dcc.Graph(id='keyword-graph',
                                 style={'height': '500px'})
                    ], style={'backgroundColor': 'white',
                             'padding': '20px',
                             'borderRadius': '8px',
                             'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
                ], style={'padding': '20px',
                          'backgroundColor': 'white',
                          'borderRadius': '8px',
                          'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ], style={'marginBottom': '30px'}),
            
            # 5. University Research Dashboard Widget
            html.Div([
                html.H2('University Research Dashboard', 
                       style={'color': '#2c3e50',
                              'borderBottom': '2px solid #3498db',
                              'paddingBottom': '10px',
                              'marginBottom': '15px',
                              'fontSize': '1.2em'}),
                
                html.Div([
                    # University Selection
                    html.Div([
                        html.Label('Select Universities to Compare', 
                                 style={'display': 'block',
                                        'marginBottom': '10px',
                                        'fontWeight': 'bold',
                                        'color': '#34495e',
                                        'fontSize': '1em'}),
                        
                        # University 1 Dropdown
                        html.Div([
                            html.Label('University 1', 
                                     style={'display': 'block',
                                            'marginBottom': '5px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Dropdown(
                                id='university1-dropdown',
                                options=[],  # Will be populated later
                                placeholder='Select first university',
                                style={'width': '100%'}
                            )
                        ], style={'flex': '1', 'marginRight': '10px'}),
                        
                        # University 2 Dropdown
                        html.Div([
                            html.Label('University 2', 
                                     style={'display': 'block',
                                            'marginBottom': '5px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Dropdown(
                                id='university2-dropdown',
                                options=[],  # Will be populated later
                                placeholder='Select second university',
                                style={'width': '100%'}
                            )
                        ], style={'flex': '1'}),
                        
                        # Compare Button
                        html.Div([
                            html.Button('Compare', 
                                      id='compare-universities-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#3498db',
                                             'color': 'white',
                                             'padding': '10px 20px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '1em',
                                             'fontWeight': 'bold',
                                             'marginTop': '25px'})
                        ], style={'marginLeft': '20px', 'alignSelf': 'flex-end'})
                    ], style={'display': 'flex', 'marginBottom': '20px', 'alignItems': 'flex-end'}),
                    
                    # Results Display
                    html.Div([
                        # Results Header
                        html.Div(id='university-comparison-header', 
                                children=[],
                                style={'marginBottom': '15px',
                                       'fontSize': '1.1em',
                                       'fontWeight': 'bold',
                                       'color': '#2c3e50',
                                       'textAlign': 'center'}),
                        
                        # Visualizations
                        html.Div([
                            # Faculty Count Chart
                            html.Div([
                                html.H3('Faculty Count',
                                       style={'color': '#34495e',
                                              'marginBottom': '10px',
                                              'fontSize': '1em',
                                              'textAlign': 'center'}),
                                dcc.Graph(id='faculty-count-chart',
                                         style={'height': '250px'})
                            ], style={'flex': '1', 'margin': '0 10px'}),
                            
                            # Publication Count Chart
                            html.Div([
                                html.H3('Publication Count',
                                       style={'color': '#34495e',
                                              'marginBottom': '10px',
                                              'fontSize': '1em',
                                              'textAlign': 'center'}),
                                dcc.Graph(id='publication-count-chart',
                                         style={'height': '250px'})
                            ], style={'flex': '1', 'margin': '0 10px'}),
                            
                            # Average Citations Chart
                            html.Div([
                                html.H3('Average Citations',
                                       style={'color': '#34495e',
                                              'marginBottom': '10px',
                                              'fontSize': '1em',
                                              'textAlign': 'center'}),
                                dcc.Graph(id='avg-citations-chart',
                                         style={'height': '250px'})
                            ], style={'flex': '1', 'margin': '0 10px'})
                        ], style={'display': 'flex', 'marginBottom': '20px'})
                    ], id='university-comparison-results', style={'display': 'none'}),
                    
                    # No Selection Message
                    html.Div(id='university-comparison-message',
                            children=['Select two universities and click Compare to see research metrics'],
                            style={'textAlign': 'center',
                                   'padding': '40px',
                                   'color': '#7f8c8d',
                                   'fontSize': '1.1em'})
                ], style={'padding': '20px',
                          'backgroundColor': 'white',
                          'borderRadius': '8px',
                          'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ], style={'marginBottom': '30px'}),
            
            # Row for Faculty Profile and Publication Submission
            html.Div([
                # 6. Faculty Profile Management Widget (left side)
                html.Div([
                    html.H2('Faculty Profile Management', 
                           style={'color': '#2c3e50',
                                  'borderBottom': '2px solid #3498db',
                                  'paddingBottom': '10px',
                                  'marginBottom': '15px',
                                  'fontSize': '1.2em'}),
                    
                    html.Div([
                        # Input fields in a more compact layout
                        html.Div([
                            html.Label('Name', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-name', 
                                    type='text', 
                                    placeholder='Enter faculty name',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Label('Position', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-position', 
                                    type='text', 
                                    placeholder='Enter position',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Label('Research Interest', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-research', 
                                    type='text', 
                                    placeholder='Enter research interests',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Label('Email', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-email', 
                                    type='email', 
                                    placeholder='Enter email',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Label('Phone', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='faculty-phone', 
                                    type='text', 
                                    placeholder='Enter phone number',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Label('University', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Dropdown(
                                id='faculty-university',
                                options=[{'label': name, 'value': id} for id, name in get_universities()],
                                placeholder='Select university',
                                style={'width': '100%',
                                       'marginBottom': '10px',
                                       'fontSize': '0.9em'}
                            )
                        ]),
                        
                        # Buttons row
                        html.Div([
                            html.Button('Add Faculty', 
                                      id='add-faculty-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#3498db',
                                             'color': 'white',
                                             'padding': '8px 16px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '0.9em',
                                             'fontWeight': 'bold',
                                             'transition': 'background-color 0.3s ease',
                                             'width': '48%',
                                             'marginRight': '4%'}),
                            
                            html.Button('Clear Fields', 
                                      id='clear-fields-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#e74c3c',
                                             'color': 'white',
                                             'padding': '8px 16px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '0.9em',
                                             'fontWeight': 'bold',
                                             'transition': 'background-color 0.3s ease',
                                             'width': '48%'})
                        ], style={'display': 'flex',
                                 'justifyContent': 'space-between',
                                 'marginBottom': '10px'}),
                        
                        # Add new output component for displaying added faculty
                        html.Div([
                            html.Div(id='add-faculty-output',
                                    style={'marginTop': '10px',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'textAlign': 'center',
                                           'fontSize': '0.9em'}),
                            
                            # New component to display added faculty record
                            html.Div(id='added-faculty-display',
                                    style={'marginTop': '15px',
                                           'padding': '15px',
                                           'backgroundColor': '#f8f9fa',
                                           'borderRadius': '8px',
                                           'border': '1px solid #e9ecef',
                                           'display': 'none'})
                        ])
                    ], style={'maxWidth': '300px',
                              'padding': '15px',
                              'backgroundColor': 'white',
                              'borderRadius': '8px',
                              'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
                ], style={'flex': '1', 'marginRight': '20px'}),
                
                # 7. Publication Submission Widget (right side)
                html.Div([
                    html.H2('Publication Submission', 
                           style={'color': '#2c3e50',
                                  'borderBottom': '2px solid #3498db',
                                  'paddingBottom': '10px',
                                  'marginBottom': '15px',
                                  'fontSize': '1.2em'}),
                    
                    html.Div([
                        # Publication Title
                        html.Div([
                            html.Label('Publication Title', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-title', 
                                    type='text', 
                                    placeholder='Enter publication title',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Venue
                        html.Div([
                            html.Label('Venue', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-venue', 
                                    type='text', 
                                    placeholder='Enter publication venue',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Year
                        html.Div([
                            html.Label('Year', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-year', 
                                    type='number', 
                                    placeholder='Enter publication year',
                                    min=1900,
                                    max=2100,
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Citations
                        html.Div([
                            html.Label('Number of Citations', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-citations', 
                                    type='number', 
                                    placeholder='Enter number of citations',
                                    min=0,
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        # Authors
                        html.Div([
                            html.Label('Authors', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Dropdown(
                                id='pub-authors',
                                options=[{'label': name, 'value': id} for id, name in get_faculty_for_dropdown()],
                                placeholder='Select authors',
                                multi=True,
                                style={'width': '100%',
                                       'marginBottom': '10px',
                                       'fontSize': '0.9em'}
                            )
                        ]),
                        
                        html.Div([
                            html.Label('Keywords', 
                                     style={'display': 'block',
                                            'marginBottom': '2px',
                                            'fontWeight': 'bold',
                                            'color': '#34495e',
                                            'fontSize': '0.9em'}),
                            dcc.Input(id='pub-keywords', 
                                    type='text', 
                                    placeholder='Enter keywords (comma-separated)',
                                    style={'width': '100%',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'border': '1px solid #bdc3c7',
                                           'marginBottom': '10px',
                                           'fontSize': '0.9em'})
                        ]),
                        
                        html.Div([
                            html.Button('Submit Publication', 
                                      id='submit-pub-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#3498db',
                                             'color': 'white',
                                             'padding': '8px 16px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '0.9em',
                                             'fontWeight': 'bold',
                                             'transition': 'background-color 0.3s ease',
                                             'width': '48%',
                                             'marginRight': '4%'}),
                            
                            html.Button('Clear Fields', 
                                      id='clear-pub-fields-button', 
                                      n_clicks=0,
                                      style={'backgroundColor': '#e74c3c',
                                             'color': 'white',
                                             'padding': '8px 16px',
                                             'border': 'none',
                                             'borderRadius': '4px',
                                             'cursor': 'pointer',
                                             'fontSize': '0.9em',
                                             'fontWeight': 'bold',
                                             'transition': 'background-color 0.3s ease',
                                             'width': '48%'})
                        ], style={'display': 'flex',
                                 'justifyContent': 'space-between',
                                 'marginBottom': '10px'}),
                        
                        # Add new output component for displaying added publication
                        html.Div([
                            html.Div(id='submit-pub-output',
                                    style={'marginTop': '10px',
                                           'padding': '8px',
                                           'borderRadius': '4px',
                                           'textAlign': 'center',
                                           'fontSize': '0.9em'}),
                            
                            # New component to display added publication record
                            html.Div(id='added-publication-display',
                                    style={'marginTop': '15px',
                                           'padding': '15px',
                                           'backgroundColor': '#f8f9fa',
                                           'borderRadius': '8px',
                                           'border': '1px solid #e9ecef',
                                           'display': 'none'})
                        ])
                    ], style={'maxWidth': '300px',
                              'padding': '15px',
                              'backgroundColor': 'white',
                              'borderRadius': '8px',
                              'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
                ], style={'flex': '1'})
            ], style={'display': 'flex',
                      'marginBottom': '30px'})
        ], style={'maxWidth': '1200px',
                  'margin': '0 auto',
                  'padding': '20px',
                  'fontFamily': 'Arial, sans-serif'})
    ])
])

# Add new callback for clearing fields
@app.callback(
    [Output('faculty-name', 'value'),
     Output('faculty-position', 'value'),
     Output('faculty-research', 'value'),
     Output('faculty-email', 'value'),
     Output('faculty-phone', 'value'),
     Output('faculty-university', 'value')],
    [Input('clear-fields-button', 'n_clicks')],
    prevent_initial_call=True
)
def clear_fields(n_clicks):
    if n_clicks > 0:
        return '', '', '', '', '', None
    return dash.no_update

# Callback for adding faculty
@app.callback(
    [Output('add-faculty-output', 'children'),
     Output('added-faculty-display', 'children'),
     Output('added-faculty-display', 'style')],
    [Input('add-faculty-button', 'n_clicks')],
    [State('faculty-name', 'value'),
     State('faculty-position', 'value'),
     State('faculty-research', 'value'),
     State('faculty-email', 'value'),
     State('faculty-phone', 'value'),
     State('faculty-university', 'value')]
)
def add_faculty(n_clicks, name, position, research, email, phone, university_id):
    if n_clicks > 0:
        if not all([name, position, research, email, university_id]):
            return (
                html.Div('Please fill in all required fields', style={'color': 'red'}),
                None,
                {'display': 'none'}
            )
        
        connection = get_mysql_connection()
        if connection:
            try:
                with connection.cursor() as cursor:
                    # Get the next available ID
                    cursor.execute("SELECT MAX(id) FROM faculty")
                    max_id = cursor.fetchone()[0]
                    new_id = max_id + 1 if max_id else 1
                    
                    # Insert new faculty
                    query = """
                    INSERT INTO faculty (id, name, position, research_interest, email, phone, university_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (new_id, name, position, research, email, phone, university_id))
                    connection.commit()
                    
                    # Get university name for display
                    cursor.execute("SELECT name FROM university WHERE id = %s", (university_id,))
                    university_name = cursor.fetchone()[0]
                    
                    # Create the display content
                    faculty_display = html.Div([
                        html.H4('Added Faculty Record', 
                               style={'color': '#2c3e50',
                                      'marginBottom': '10px',
                                      'textAlign': 'center'}),
                        html.Div([
                            html.Div([
                                html.Strong('ID: '), str(new_id)
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('Name: '), name
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('Position: '), position
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('Research Interest: '), research
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('Email: '), email
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('Phone: '), phone or 'Not provided'
                            ], style={'marginBottom': '5px'}),
                            html.Div([
                                html.Strong('University: '), university_name
                            ])
                        ], style={'padding': '10px'})
                    ])
                    
                    return (
                        html.Div('Faculty added successfully!', style={'color': 'green'}),
                        faculty_display,
                        {'display': 'block'}
                    )
            except Exception as e:
                return (
                    html.Div(f'Error adding faculty: {str(e)}', style={'color': 'red'}),
                    None,
                    {'display': 'none'}
                )
            finally:
                connection.close()
        return (
            html.Div('Error connecting to database', style={'color': 'red'}),
            None,
            {'display': 'none'}
        )
    return '', None, {'display': 'none'}

# Add callback for clearing publication fields
@app.callback(
    [Output('pub-title', 'value'),
     Output('pub-venue', 'value'),
     Output('pub-year', 'value'),
     Output('pub-citations', 'value'),
     Output('pub-authors', 'value'),
     Output('pub-keywords', 'value')],
    [Input('clear-pub-fields-button', 'n_clicks')],
    prevent_initial_call=True
)
def clear_pub_fields(n_clicks):
    if n_clicks > 0:
        return '', '', None, None, [], ''
    return dash.no_update

# Add callback for submitting publication
@app.callback(
    [Output('submit-pub-output', 'children'),
     Output('added-publication-display', 'children'),
     Output('added-publication-display', 'style')],
    [Input('submit-pub-button', 'n_clicks')],
    [State('pub-title', 'value'),
     State('pub-venue', 'value'),
     State('pub-year', 'value'),
     State('pub-citations', 'value'),
     State('pub-authors', 'value'),
     State('pub-keywords', 'value')]
)
def submit_publication(n_clicks, title, venue, year, citations, authors, keywords):
    if n_clicks > 0:
        if not all([title, venue, year, authors]):
            return (
                html.Div('Please fill in all required fields', style={'color': 'red'}),
                None,
                {'display': 'none'}
            )
        
        try:
            db = get_mongodb_connection()
            if db is not None:
                # Get the next available ID
                last_pub = db.publications.find_one(sort=[("id", -1)])
                new_id = (last_pub["id"] + 1) if last_pub else 1
                
                # Process keywords
                keyword_list = [{"name": k.strip()} for k in keywords.split(',')] if keywords else []
                
                # Create publication document
                publication = {
                    "id": new_id,
                    "title": title,
                    "venue": venue,
                    "year": year,
                    "numCitations": citations or 0,
                    "keywords": keyword_list,
                    "authors": authors
                }
                
                # Insert into MongoDB
                db.publications.insert_one(publication)
                
                # Get author names for display
                connection = get_mysql_connection()
                author_names = []
                if connection:
                    try:
                        with connection.cursor() as cursor:
                            for author_id in authors:
                                cursor.execute("SELECT name FROM faculty WHERE id = %s", (author_id,))
                                result = cursor.fetchone()
                                if result:
                                    author_names.append(result[0])
                    finally:
                        connection.close()
                
                # Create the display content
                publication_display = html.Div([
                    html.H4('Added Publication Record', 
                           style={'color': '#2c3e50',
                                  'marginBottom': '10px',
                                  'textAlign': 'center'}),
                    html.Div([
                        html.Div([
                            html.Strong('ID: '), str(new_id)
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Title: '), title
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Venue: '), venue
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Year: '), str(year)
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Citations: '), str(citations or 0)
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Authors: '), ', '.join(author_names)
                        ], style={'marginBottom': '5px'}),
                        html.Div([
                            html.Strong('Keywords: '), 
                            html.Div([
                                html.Span(
                                    keyword['name'],
                                    style={
                                        'display': 'inline-block',
                                        'padding': '3px 8px',
                                        'backgroundColor': '#3498db',
                                        'color': 'white',
                                        'borderRadius': '12px',
                                        'margin': '3px',
                                        'fontSize': '0.85em'
                                    }
                                ) for keyword in keyword_list
                            ])
                        ])
                    ], style={'padding': '10px'})
                ])
                
                return (
                    html.Div('Publication submitted successfully!', style={'color': 'green'}),
                    publication_display,
                    {'display': 'block'}
                )
        except Exception as e:
            return (
                html.Div(f'Error submitting publication: {str(e)}', style={'color': 'red'}),
                None,
                {'display': 'none'}
            )
    return '', None, {'display': 'none'}

# Helper function to get faculty by ID
def get_faculty_by_id(faculty_id):
    connection = get_mysql_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = "SELECT * FROM faculty WHERE id = %s"
                cursor.execute(query, (faculty_id,))
                columns = [desc[0] for desc in cursor.description]
                result = cursor.fetchone()
                if result:
                    return dict(zip(columns, result))
        except Exception as e:
            print(f"Error fetching faculty: {e}")
        finally:
            connection.close()
    return None

# Add callback for publication search
@app.callback(
    Output('publication-table', 'data'),
    [Input('pub-search', 'value'),
     Input('min-citations', 'value'),
     Input('year-range', 'value')]
)
def update_publication_table(search_term, min_citations, year_range):
    publications = get_publications(search_term, min_citations, year_range)
    return publications

# Add callback for network visualization
@app.callback(
    Output('network-graph', 'figure'),
    [Input('faculty-search', 'value'),
     Input('node-size', 'value'),
     Input('link-strength', 'value')]
)
def update_network(faculty_name, node_size, link_strength):
    # Get collaboration data
    collaborations = get_collaboration_network(faculty_name)
    
    if not collaborations:
        # Return empty figure if no data
        return go.Figure().update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=500,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            annotations=[dict(
                text="No collaborations found. Try another faculty name.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )]
        )
    
    # Create nodes and edges
    nodes = set()
    edges = []
    for record in collaborations:
        nodes.add(record['source'])
        nodes.add(record['target'])
        edges.append({
            'source': record['source'],
            'target': record['target'],
            'value': record['weight']
        })
    
    # Create network graph using networkx for layout
    G = nx.Graph()
    
    # Add nodes and edges
    for node in nodes:
        G.add_node(node)
    for edge in edges:
        G.add_edge(edge['source'], edge['target'], weight=edge['value'])
    
    # Generate layout with improved parameters
    pos = nx.spring_layout(
        G,
        k=2,  # Increased node repulsion
        iterations=100,  # More iterations for better layout
        scale=2,  # Larger scale for more spacing
        seed=42  # Fixed seed for consistent layout
    )
    
    # Create edge traces with improved styling
    edge_traces = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        weight = G[edge[0]][edge[1]]['weight']
        
        # Get node names for better hover text
        source_node = edge[0]
        target_node = edge[1]
        
        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(
                width=min(weight * link_strength * 0.5, 5),
                color='rgba(52, 152, 219, 0.2)'
            ),
            hovertemplate=f"{source_node} & {target_node}<br>Papers together: {weight}<extra></extra>",
            hoverlabel=dict(
                bgcolor='#FFF',
                font_size=14,
                font_family="Arial",
                bordercolor='#3498db'
            ),
            showlegend=False
        )
        edge_traces.append(edge_trace)
    
    # Create node trace with improved styling
    node_trace = go.Scatter(
        x=[pos[node][0] for node in G.nodes()],
        y=[pos[node][1] for node in G.nodes()],
        mode='markers+text',
        text=list(G.nodes()),
        textposition="middle center",
        textfont=dict(
            size=12,
            color='black'
        ),
        marker=dict(
            size=node_size * 2,
            color='#3498db',
            line=dict(width=2, color='white')
        ),
        hoverinfo='skip',  # Skip node hover to make edge hover more prominent
        showlegend=False
    )
    
    # Create figure
    fig = go.Figure(data=edge_traces + [node_trace])
    
    # Update layout with improved parameters
    fig.update_layout(
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=40, r=40, t=40, b=40),
        height=500,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-1.2, 1.2]
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-1.2, 1.2]
        ),
        hovermode='closest',
        hoverdistance=10,  # Make hover more sensitive
        dragmode='pan'
    )
    
    return fig

# Update the callback for keyword visualization
@app.callback(
    [Output('keyword-frequency-chart', 'figure'),
     Output('keyword-graph', 'figure'),
     Output('keyword-chart-title', 'children')],
    [Input('keyword-search-button', 'n_clicks')],
    [State('keyword-search', 'value')]
)
def update_keyword_visualizations(n_clicks, search_term):
    # Get keyword data
    data = get_keyword_relationships(search_term if search_term else None)
    
    # Update chart title based on search
    if data['search_term']:
        chart_title = f"Top 10 Keywords Related to '{data['search_term']}'"
    else:
        chart_title = "Top 10 Most Frequent Keywords"
    
    # Create frequency bar chart
    freq_fig = go.Figure()
    if data['top_keywords']:
        freq_fig.add_trace(go.Bar(
            x=[record['keyword'] for record in data['top_keywords']],
            y=[record['frequency'] for record in data['top_keywords']],
            marker_color='#3498db',
            hovertemplate='<b>%{x}</b><br>Frequency: %{y}<extra></extra>'
        ))
    
    freq_fig.update_layout(
        xaxis_title='Keyword',
        yaxis_title='Number of Publications',
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    # Create co-occurrence network
    if not data['relationships']:
        message = "No keyword relationships found."
        if data['search_term']:
            message = f"No relationships found for '{data['search_term']}'."
            
        network_fig = go.Figure().update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=500,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            annotations=[dict(
                text=message,
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )]
        )
    else:
        # Create nodes and edges
        nodes = set()
        edges = []
        for record in data['relationships']:
            nodes.add(record['source'])
            nodes.add(record['target'])
            edges.append({
                'source': record['source'],
                'target': record['target'],
                'value': record['weight']
            })
        
        # Create network graph
        G = nx.Graph()
        for node in nodes:
            G.add_node(node)
        for edge in edges:
            G.add_edge(edge['source'], edge['target'], weight=edge['value'])
        
        # Generate layout
        pos = nx.spring_layout(G, k=1.5, iterations=100, seed=42)
        
        # Create edge traces
        edge_traces = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            weight = G[edge[0]][edge[1]]['weight']
            
            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(
                    width=min(weight * 0.5, 5),
                    color='rgba(46, 204, 113, 0.3)'
                ),
                hovertemplate=f"{edge[0]} & {edge[1]}<br>Shared publications: {weight}<extra></extra>",
                hoverlabel=dict(
                    bgcolor='#FFF',
                    font_size=14,
                    font_family="Arial",
                    bordercolor='#2ecc71'
                ),
                showlegend=False
            )
            edge_traces.append(edge_trace)
        
        # Highlight the searched keyword with a different color if it exists in the graph
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if data['search_term'] and node == data['search_term']:
                node_colors.append('#e74c3c')  # Red for searched keyword
                node_sizes.append(30)  # Larger size for searched keyword
            else:
                node_colors.append('#2ecc71')  # Green for other keywords
                node_sizes.append(20)  # Normal size for other keywords
        
        # Create node trace
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G.nodes()],
            y=[pos[node][1] for node in G.nodes()],
            mode='markers+text',
            text=list(G.nodes()),
            textposition="middle center",
            textfont=dict(
                size=12,
                color='black'
            ),
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2, color='white')
            ),
            hoverinfo='skip',
            showlegend=False
        )
        
        # Create figure
        network_fig = go.Figure(data=edge_traces + [node_trace])
        
        # Update layout
        network_fig.update_layout(
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=40, r=40, t=40, b=40),
            height=500,
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-1.2, 1.2]
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-1.2, 1.2]
            ),
            hovermode='closest',
            hoverdistance=10,
            dragmode='pan'
        )
    
    return freq_fig, network_fig, chart_title

# Add callback for university comparison
@app.callback(
    [Output('university-comparison-header', 'children'),
     Output('university-comparison-results', 'style'),
     Output('university-comparison-message', 'style'),
     Output('faculty-count-chart', 'figure'),
     Output('publication-count-chart', 'figure'),
     Output('avg-citations-chart', 'figure')],
    [Input('compare-universities-button', 'n_clicks')],
    [State('university1-dropdown', 'value'),
     State('university2-dropdown', 'value')]
)
def compare_universities(n_clicks, uni1_id, uni2_id):
    if n_clicks > 0 and uni1_id and uni2_id:
        # Get university data
        uni_data = get_university_research_data([uni1_id, uni2_id])
        
        if len(uni_data) < 2:
            # Not enough data
            return (
                f"Error: Could not retrieve data for the selected universities",
                {'display': 'none'},
                {'display': 'block', 'textAlign': 'center', 'padding': '40px', 'color': '#e74c3c', 'fontSize': '1.1em'},
                go.Figure(),
                go.Figure(),
                go.Figure()
            )
        
        # Extract data for charts
        uni_names = [uni['name'] for uni in uni_data]
        faculty_counts = [uni['faculty_count'] for uni in uni_data]
        pub_counts = [uni['publication_count'] for uni in uni_data]
        avg_citations = [uni['avg_citations'] for uni in uni_data]
        
        # Create faculty count chart
        faculty_fig = go.Figure()
        faculty_fig.add_trace(go.Bar(
            x=uni_names,
            y=faculty_counts,
            marker_color=['#3498db', '#2ecc71'],
            text=faculty_counts,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Faculty: %{y}<extra></extra>'
        ))
        faculty_fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=30, r=30, t=30, b=30),
            yaxis_title='Number of Faculty'
        )
        
        # Create publication count chart
        pub_fig = go.Figure()
        pub_fig.add_trace(go.Bar(
            x=uni_names,
            y=pub_counts,
            marker_color=['#3498db', '#2ecc71'],
            text=pub_counts,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Publications: %{y}<extra></extra>'
        ))
        pub_fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=30, r=30, t=30, b=30),
            yaxis_title='Number of Publications'
        )
        
        # Create average citations chart
        citations_fig = go.Figure()
        citations_fig.add_trace(go.Bar(
            x=uni_names,
            y=avg_citations,
            marker_color=['#3498db', '#2ecc71'],
            text=[f"{cit:.2f}" for cit in avg_citations],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Avg Citations: %{text}<extra></extra>'
        ))
        citations_fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=30, r=30, t=30, b=30),
            yaxis_title='Average Citations per Publication'
        )
        
        return (
            f"Comparing Research Output: {uni_names[0]} vs {uni_names[1]}",
            {'display': 'block'},
            {'display': 'none'},
            faculty_fig,
            pub_fig,
            citations_fig
        )
    
    # Default state (no comparison yet)
    return (
        "",
        {'display': 'none'},
        {'display': 'block', 'textAlign': 'center', 'padding': '40px', 'color': '#7f8c8d', 'fontSize': '1.1em'},
        go.Figure(),
        go.Figure(),
        go.Figure()
    )

# Add callback to populate university dropdowns
@app.callback(
    [Output('university1-dropdown', 'options'),
     Output('university2-dropdown', 'options')],
    [Input('_', 'children')]
)
def populate_university_dropdowns(_):
    try:
        universities = get_university_research_data()
        options = [{'label': name, 'value': id} for id, name in universities]
        return options, options
    except Exception as e:
        return [], []

# Add callback to populate faculty dropdown
@app.callback(
    Output('faculty-summary-dropdown', 'options'),
    [Input('_', 'children')]
)
def populate_faculty_dropdown(_):
    try:
        faculty_list = get_faculty_for_dropdown()
        options = [{'label': name, 'value': id} for id, name in faculty_list]
        return options
    except Exception as e:
        return []

# Add callback for faculty summary display
@app.callback(
    [Output('faculty-summary-header', 'children'),
     Output('faculty-summary-content', 'style'),
     Output('faculty-position-display', 'children'),
     Output('faculty-university-display', 'children'),
     Output('faculty-email-display', 'children'),
     Output('faculty-publications-display', 'children'),
     Output('faculty-interest-display', 'children'),
     Output('faculty-keywords-display', 'children')],
    [Input('view-faculty-button', 'n_clicks')],
    [State('faculty-summary-dropdown', 'value')]
)
def display_faculty_summary(n_clicks, faculty_id):
    if n_clicks > 0 and faculty_id:
        # Get faculty data
        faculty_data = get_faculty_summary(faculty_id)
        
        if faculty_data:
            # Prepare keyword badges
            keyword_badges = []
            for keyword in faculty_data.get('keywords', []):
                badge = html.Span(
                    keyword['name'],
                    style={
                        'display': 'inline-block',
                        'padding': '5px 10px',
                        'backgroundColor': '#3498db',
                        'color': 'white',
                        'borderRadius': '15px',
                        'margin': '3px',
                        'fontSize': '0.85em'
                    }
                )
                keyword_badges.append(badge)
            
            # Return faculty data for display
            return (
                faculty_data['name'],  # Header
                {'display': 'block'},  # Content visibility
                faculty_data['position'],  # Position
                faculty_data['university_name'] or 'Not affiliated',  # University
                faculty_data['email'] or 'No email provided',  # Email
                str(faculty_data['publication_count']),  # Publication count
                faculty_data['research_interest'] or 'Not specified',  # Research interest
                keyword_badges  # Keywords as badges
            )
        
        # If faculty not found
        return (
            "Faculty not found",
            {'display': 'block'},
            "N/A",
            "N/A",
            "N/A",
            "0",
            "N/A",
            []
        )
    
    # Default state (no faculty selected)
    return (
        "",
        {'display': 'none'},
        "",
        "",
        "",
        "",
        "",
        []
    )

if __name__ == '__main__':
    app.run_server(debug=True) 