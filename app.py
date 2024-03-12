from flask import Flask, render_template, request, redirect, url_for, session, flash
from newspaper import Article
import nltk
from nltk import sent_tokenize, word_tokenize, pos_tag
from collections import Counter
import json
import psycopg2
from authlib.integrations.flask_client import OAuth


# Download NLTK data
nltk.download('all')

# Initialize Flask app
app = Flask(__name__)
oauth = OAuth(app)
app.secret_key = 'your_secret_key'

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="dpg-cnmthkmn7f5s73d8uh0g-a",
    database="news_analysis",
    user="suresh",
    password="oLb1dOwhXPx19klUls6XZTpd9oO1zGAI"
)
cur = conn.cursor()

app.config['SECRET_KEY'] = "suresh_secret_key"
app.config['GITHUB_CLIENT_ID'] = "d40134cef5babd6c5ce4"
app.config['GITHUB_CLIENT_SECRET'] = "5b717ab28ec76ad97de267e28ccd1b817df0e280"

github = oauth.register(
    name='github',
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)
github_admin_usernames = ["sureshpanwar777", "atmabodha"]

@app.route('/admin_route')
def admin_route():
    is_admin = False
    github_token = session.get('github_token')
    if github_token:
        github = oauth.create_client('github')
        resp = github.get('user').json()
        username = resp.get('login')
        if username in github_admin_usernames:
            is_admin = True
    return render_template('login.html', logged_in=github_token is not None, is_admin=is_admin)
    
@app.route('/login/github')
def github_login():
    github = oauth.create_client('github')
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/login/github/authorize')
def github_authorize():
    github = oauth.create_client('github')
    token = github.authorize_access_token()
    session['github_token'] = token
    resp = github.get('user').json()
    print(f"\n{resp}\n")

    if 'login' in resp:
        username = resp['login']
        if username in github_admin_usernames:
            analysis_data = fetch_analysis_data()
            return render_template('admin_dashboard.html', analysis_data=analysis_data)
        else:
            return f'you are not authorized to access this page'
    else:
        return f'Unable to fetch github username'

@app.route('/logout/github')
def github_logout():
    session.pop('github_token', None)
    return redirect(url_for('home'))




def create_table():
    """Create a table if it doesn't exist"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS newsdata (
            id SERIAL PRIMARY KEY,
            url VARCHAR(255),
            title VARCHAR(255),
            content TEXT,
            num_sentences INTEGER,
            num_words INTEGER,
            pos_counts JSON
        )
    """)
    conn.commit()

def fetch_news_content(url):
    """Fetch news content from the given URL"""
    try:
        # Fetch HTML content using newspaper library
        article = Article(url)
        article.download()
        article.parse()

        title = article.title if article.title else 'Title not found'
        text = article.text if article.text else 'Content not found'
        images = article.images if article.images else []

        return title, text, images
    except Exception as e:
        print(f"Error fetching content: {e}")
        return None, None, None

def analyze_text(text):
    """Analyze text content"""
    # Tokenize text into sentences
    sentences = sent_tokenize(text)
    
    # Count number of sentences and words
    num_sentences = len(sentences)
    words = word_tokenize(text)
    num_words = len(words)
    
    # Tag words with POS
    POS_tags = pos_tag(words,  tagset='universal')
    
    # Count POS tags
    postag_counts = Counter(tag for word, tag in POS_tags)
    
    return num_sentences, num_words, postag_counts

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        # For simplicity, you can use a hardcoded username and password here
        if request.form['username'] == 'suresh' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    """Handle user logout"""
    session.pop('logged_in', None)
    return redirect(url_for('home'))

# Protected route (requires authentication)
@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if 'logged_in' in session and session['logged_in']:
        # Fetch past analyses from the database
        cur.execute("SELECT * FROM newsdata")
        past_analyses = cur.fetchall()
        return render_template('admin_dashboard.html', past_analyses=past_analyses)
    else:
        return redirect(url_for('login'))

# Home route
@app.route('/')
def home():
    """Home page"""
    return render_template('index.html')

@app.route('/result', methods=['GET', 'POST'])
def result():
    """Handle result"""
    if request.method == 'POST':
        url = request.form.get('newsurl')
        if url:
            title, content, images = fetch_news_content(url)

            # Check if the fetch was successful
            if title is None or content is None or images is None:
                flash("Error fetching content. Please check the URL and try again.", 'error')
            else:
                num_sentences, num_words, pos_counts = analyze_text(content)
                pos_counts_json = json.dumps(pos_counts)

                create_table()
                cur.execute("""
                    INSERT INTO newsdata (url, title, content, num_sentences, num_words, pos_counts)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (url, title, content, num_sentences, num_words, pos_counts_json))

                conn.commit()

                # Render the result template with the analysis details
                return render_template('result.html', title=title, content=content,
                                    num_sentences=num_sentences, num_words=num_words, pos_counts=pos_counts)

if __name__ == '__main__':
    app.run(debug=True)
    cur.close()
    conn.close()
