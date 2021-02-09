# IzzyWishlist
Simple wishlist project to add, save and view desired PS games more easily.

Work in progress, by Ivan Silva and Carlos Zgierski.

# Folder Structure
The following items describe the folder structure and what they contain.

- **source_code**: contains the code for the application. Initially this will be composed of Python/Django code;
  - **izzywishlist**: main folder of the **Django Project** initialized using the Django routines;
    - **playsapp**: folder of the application for the wishlist of PS games. Created as a **Django App**, considering that each new gaming platform may be a new app in the future;
  - **prototypes**: a common folder for uploading prototype python scripts for discussion;
- **specification**: contains documents with the description of the steps of development for achieving each individual goal we establish;
- Anything other than the described folders is default Django Project structure and will not be described here.

# Running Django Project
- Open a console at the following location:

./source_code/izzywishlist/

- Run one of the following commands depending on the TCP port requirements:

python manage.py runserver

python manage.py runserver 9090

- To access, open a browser and type the address:

http://localhost:8000

http://localhost: < port >