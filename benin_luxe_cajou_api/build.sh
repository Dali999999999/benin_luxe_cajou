#!usrbinenv bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Cette commande est juste pour synchroniser l'état de la migration, elle ne modifiera pas votre base.
# flask db stamp head 