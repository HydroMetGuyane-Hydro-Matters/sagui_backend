import pandas as pd
import datetime
import os

'''
Script de production des sé&ries de référence, à partir de la liste des valeurs quotidiennes, générées par un run MGB. 
Aggrège les valeurs de débit par jour de l'année, pour chaque tranche de 10 ans
Produit le résultat  sous deux formats : pivoté (une colonne par station) ou en mode key,value
'''


csv_file='/home/jean/PRO/projets_encours/2022-IRD-Hydromatters/sagui/data/stations/MGB-HYFAA_MSWEP_Guyane_1980-2020_Q_R.csv'
conversion_factors='https://docs.google.com/spreadsheets/d/e/2PACX-1vSYUw5m-asL1Q_QHOvx6AO1NAzT-iuuSm8pxKjiAO4M2FvKIac97nT_yw9hkl0sNOYBgbo3WvW5Jvbn/pub?gid=0&single=true&output=csv'
apply_conversion_factor = True

parser = lambda date: datetime.datetime.strptime(date, '%Y-%m-%d')
df = pd.read_csv(csv_file, sep=',', parse_dates=['date'], date_parser=parser, dtype={'Mini': 'int', 'Q':'float'})

df.rename(columns={"Mini": "mini", "Q": "flow"}, inplace=True)

# Filter out data that are too recent
df = df[df['date'].dt.date < datetime.date(2020, 1, 1)]

# Add the period column, computed from the dates
def year_to_period(d):
    import numpy
    start_decade = int(numpy.floor(d/10))
    end_decade = int(numpy.floor(d/10) + 1)
    return '{}0-{}0'.format(start_decade, end_decade)
year_to_period(1995)
df['ref_period'] = df["date"].dt.year.apply(year_to_period)

# Add the day-of-year column
df['day_of_year'] = df["date"].dt.dayofyear

# Calculate the mean value over the periods
dff = df.groupby(['ref_period','mini', 'day_of_year']).mean()
# dff['conv'] = dff['flow']

if apply_conversion_factor:
    # Apply conversion factors to match in-situ data
    # We tap directly into the Google sheet, exposed as CSV
    # Load the csv into a pandas dataframe
    conv_fact = pd.read_csv(conversion_factors, sep=',', skip_blank_lines=True, dtype={'minibasin_mgb': 'str', 'conversion*****':'str'})
    conv_fact = conv_fact[conv_fact['minibasin_mgb'] != 'Nan']
    # Convert it into a dict, easier to use
    conv_factors = dict()
    conv_fact.reset_index()
    for row in conv_fact.iterrows():
        conv_factors[row[1]['minibasin_mgb']] = row[1]['conversion*****']

    def apply_conv_factor(conv_factors: dict, minibasin_id: str, flow: float):
        f = flow
        val = eval(conv_factors[minibasin_id])
        return val

    # df['conv'] = apply_conv_factor(conv_factors, df['mini'], df['flow'])

    for row in dff.iterrows():
        mini = row[0][1]
        # row[1]['conv'] = apply_conv_factor(conv_factors, str(mini), row[1]['flow'])
        row[1]['flow'] = apply_conv_factor(conv_factors, str(mini), row[1]['flow'])

    # [hack] Since Adrien's algorithm might generate some negative values, for now, we will "clip" them to 0
    dff.clip(lower=0, inplace=True)

df2 = dff.round(1)

# Reshape the table
df3 = df2.pivot_table(index=['ref_period','day_of_year'],columns='mini',values='flow')

# Write back to CSV
# Write key-value table
out_file = os.path.splitext(csv_file)[0]+'_ref_data_kv.csv'
df2.to_csv(out_file)
print('key-value format written to {}'.format(out_file))
# Write pivoted table
out_file = os.path.splitext(csv_file)[0]+'_ref_data_pivot_table.csv'
df3.to_csv(out_file)
print('pivot-table format written to {}'.format(out_file))