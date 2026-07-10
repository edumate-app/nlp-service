import torch
from functools import partial

# Wymuszamy, aby każde wywołanie torch.load domyślnie ustawiało weights_only=False
torch.load = partial(torch.load, weights_only=False)

# Teraz importujemy biblioteki NLP
import spacy_stanza
from spacy import displacy
nlp = spacy_stanza.load_pipeline("pl")
text ="Radomska policja przekazała informacje o wstępnych ustaleniach, dotyczących przyczyn kolizji. Radiowóz wyprzedzał pojazdy, mając włączone sygnały uprzywilejowania, natomiast kierująca VW rozpoczęła manewr skrętu w lewo. W wyniku zderzenia radiowóz uderzył w ogrodzenie posesji, a VW wjechał do rowu - czytamy. Jak dodano, oba samochody, które brały udział w zdarzeniu, poruszały się od Radomia w kierunku Zakrzewa.Mustanga skonfiskowano pijanemu kierowcy Radiowóz rozpoczął służbę w radomskiej w marcu. Pochodził z przepadku, orzeczonego wobec kierowcy, który prowadził pod wpływem alkoholu. Policja - biorąc pod uwagę dobry stan techniczny samochodu - zawnioskowała o przekazanie jej skonfiskowanego pojazdu. Sąd wyraził zgodę. Ford Mustang został przemalowany na policyjne barwy i był wykorzystywany przez radomskich funkcjonariuszy. Jak podkreślano, był to pierwszy samochód tego modelu na wyposażeniu policji."


doc = nlp(text)
print(f"\n{'CZASOWNIK':<15} | {'OSOBA':<10} | {'CZAS':<10} | {'TRYB'}")
print("-" * 50)

for token in doc:
    if token.pos_ == "VERB":
        # Pobieranie cech morfologicznych
        morph = token.morph
        print(f"{token.text:<15} | {morph.get('Person', ['-'])[0]:<10} | "
              f"{morph.get('Tense', ['-'])[0]:<10} | {morph.get('Mood', ['-'])[0]}")

# 4. Wizualizacja drzewa zależności
html = displacy.render(doc,style='dep',jupyter=False,options={'compact': True, 'distance': 120})
with open("wizualizacja.html","w",encoding='utf-8') as file:
    file.write(html)
    print("Wizualizacja zapisana")