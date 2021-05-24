"""
Fill out this file with the correct parameters, and copy to parameters.py
"""

# Authentication URL; where your browser goes when you click 'Sign In' on Moodle
url_auth = "https://auth.example.ac.uk/login"
url_moodle = "https://moodle-archive-2018-19.example.ac.uk"

# Your auth username
username = ""

# Your auth password (plaintext)
password = ""

# This form item encodes the Moodle destination (e.g. if you are going to an archive Moodle)
# It must be set correctly to get the right cookies for login!
# Get it by:
#   1. Go to the Moodle page you want to access
#   2. Click 'Sign In'
#   3. Inspect the login page form
#   4. There is a hidden input element with name="execution", copy the 'value'
execution = ""

# The course ID to clone
course_id = "123"
