from flask import Flask, render_template_string
import markdown
import os
from feeder.models import Session, NewsBrief # Import models

app = Flask(__name__)

@app.route('/')
def home():
    session = Session() # Create a database session
    try:
        # Query the database for the latest news brief
        latest_brief = session.query(NewsBrief).order_by(NewsBrief.created_at.desc()).first()

        if latest_brief:
            content = latest_brief.content
            # Convert markdown to HTML
            html_content = markdown.markdown(content)
        else:
            html_content = "<p>No news briefs found in the database.</p>"

        # Create a simple HTML template
        template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>News Brief</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    max-width: 800px;
                    margin: 0 auto;
                    color: #333;
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }
                h2 {
                    color: #3498db;
                    margin-top: 30px;
                }
                h3 {
                    color: #2980b9;
                }
                p {
                    margin-bottom: 20px;
                }
                em {
                    color: #7f8c8d;
                }
                hr {
                    border: none;
                    border-top: 1px solid #eee;
                    margin: 30px 0;
                }
            </style>
        </head>
        <body>
            {{ content|safe }}
        </body>
        </html>
        '''

        return render_template_string(template, content=html_content)
    except Exception as e:
        return f"Error loading news brief from database: {str(e)}"
    finally:
        session.close() # Close the database session

if __name__ == '__main__':
    # Ensure the port is different if the previous app is still running
    app.run(debug=True, host='0.0.0.0', port=5001) 