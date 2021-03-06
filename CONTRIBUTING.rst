.. highlight:: shell

    ============
    Contributing
    ============
    
    Contributions are welcome, and they are greatly appreciated! Every little bit
    helps, and credit will always be given.
    
    You can contribute in many ways:
    
    Types of Contributions
    ----------------------
    
    Report Bugs
    ~~~~~~~~~~~
    
    Report bugs at https://github.com/eddienko/owl-pipeline-server/issues.
    
    If you are reporting a bug, please include:
    
    * Your operating system name and version.
    * Any details about your local setup that might be helpful in troubleshooting.
    * Detailed steps to reproduce the bug.
    
    Fix Bugs
    ~~~~~~~~
    
    Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
    wanted" is open to whoever wants to implement it.
    
    Implement Features
    ~~~~~~~~~~~~~~~~~~
    
    Look through the GitHub issues for features. Anything tagged with "enhancement"
    and "help wanted" is open to whoever wants to implement it.
    
    Write Documentation
    ~~~~~~~~~~~~~~~~~~~
    
    We could always use more documentation, whether as part of the
    official docs, in docstrings, or even on the web in blog posts,
    articles, and such. There is a separate project for the documentation in
    https://github.com/eddienko/owl-pipeline
    
    Submit Feedback
    ~~~~~~~~~~~~~~~
    
    The best way to send feedback is to file an issue at
    https://github.com/eddienko/owl-pipeline-server/issues.
    
    If you are proposing a feature:
    
    * Explain in detail how it would work.
    * Keep the scope as narrow as possible, to make it easier to implement.
    * Remember that this is a volunteer-driven project, and that contributions
      are welcome :)

    Participate in the Discussion
    -----------------------------

    For everything else head to the discussion section
    in https://github.com/eddienko/owl-pipeline-server/discussions.
    
    Get Started!
    ------------
    
    Ready to contribute? Here's how to set up owl-pipeline-server for local development.
    
    1. Fork the owl-pipeline-server repo on GitHub.
    2. Clone your fork locally::
    
        $ git clone git@github.com:your_name_here/owl-pipeline-server.git
    
    3. Install your local copy into a virtualenv. Assuming you have virtualenvwrapper installed, this is how you set up your fork for local development::
    
        $ mkvirtualenv owl-pipeline-server
        $ cd owl-pipeline-server/
        $ pip install -r requirements_dev.txt
        $ python setup.py develop
    
    4. Create a branch for local development::
    
        $ git checkout -b name-of-your-bugfix-or-feature
    
       Now you can make your changes locally.
    
    5. When you're done making changes, check that your changes pass flake8::
    
        $ flake8 owl_server
        
    6. Commit your changes and push your branch to GitHub::
    
        $ git add .
        $ git commit -m "Your detailed description of your changes."
        $ git push origin name-of-your-bugfix-or-feature
    
    7. Submit a pull request through the GitHub website.
    
