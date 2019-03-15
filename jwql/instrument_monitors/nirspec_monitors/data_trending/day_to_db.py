import statistics
import os
import glob
import jwql.instrument_monitors.nirspec_monitors.data_trending.utils.mnemonics as mn
import jwql.instrument_monitors.nirspec_monitors.data_trending.utils.sql_interface as sql
import jwql.instrument_monitors.nirspec_monitors.data_trending.utils.csv_to_AstropyTable as apt
from jwql.utils.utils import get_config, filename_parser

from astropy.table import Table, Column

from jwql.instrument_monitors.nirspec_monitors.data_trending.utils.process_data import whole_day_routine

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

#point to the directory where your files are located!
directory = '/home/daniel/STScI/trainigData/nirspec_new_day/'

#here some some files contain the same data but they are all incomplete
#in order to generate a full database we have to import all of them
filenames = glob.glob(os.path.join(directory, '*.CSV'))
#test = "FOFTLM2019073163734099.CSV"

def process_file(conn, path):
    '''Parse CSV file, process data within and put to DB
    Parameters
    ----------
    conn : DBobject
        Connection object to temporary database
    path : str
        defines path to the files
    '''

    #import mnemonic data and append dict to variable below
    m_raw_data = apt.mnemonics(path)

    #process raw data with once a day routine
    cond1, cond2, cond3, cond4 = whole_day_routine(m_raw_data)

    #put all data in a database that uses a condition
    for key, value in cond1.items():
        m = m_raw_data.mnemonic(key)
        length = len(value)
        mean = statistics.mean(value)
        deviation = statistics.stdev(value)
        dataset = (float(m.meta['start']), float(m.meta['end']), length, mean, deviation)
        sql.add_data(conn, key, dataset)


    for key, value in cond2.items():
        m = m_raw_data.mnemonic(key)
        length = len(value)
        mean = statistics.mean(value)
        deviation = statistics.stdev(value)
        dataset = (float(m.meta['start']), float(m.meta['end']), length, mean, deviation)
        sql.add_data(conn, key, dataset)


    for key, value in cond3.items():
        m = m_raw_data.mnemonic(key)
        length = len(value)
        mean = statistics.mean(value)
        deviation = statistics.stdev(value)
        dataset = (float(m.meta['start']), float(m.meta['end']), length, mean, deviation)
        sql.add_data(conn, key, dataset)


    for key, value in cond4.items():
        m = m_raw_data.mnemonic(key)
        length = len(value)
        mean = statistics.mean(value)
        deviation = statistics.stdev(value)
        dataset = (float(m.meta['start']), float(m.meta['end']), length, mean, deviation)
        sql.add_data(conn, key, dataset)


    #add rest of the data to database
    for identifier in mn.mnemSet_day:
        m = m_raw_data.mnemonic(identifier)
        temp = []
        #look for all values that fit to the given conditions
        for element in m:
            temp.append(float(element['value']))
        #return None if no applicable data was found
        if len(temp) > 2:
            length = len(temp)
            mean = statistics.mean(temp)
            deviation = statistics.stdev(temp)
            dataset = (float(m.meta['start']), float(m.meta['end']), length, mean, deviation)
            sql.add_data(conn, identifier, dataset)
        else:
            print('No data for {}'.format(identifier))
        del temp


def main():
    #generate paths
    DATABASE_LOCATION = os.path.join(get_config()['jwql_dir'], 'database')
    DATABASE_FILE = os.path.join(DATABASE_LOCATION, 'nirspec_database.db')

    #connect to temporary database
    conn = sql.create_connection(DATABASE_FILE)

    '''
    path = directory + test
    process_file(conn, path)
    '''
    #do for every file in list above
    for path in filenames:
        process_file(conn, path)

    #close connection
    sql.close_connection(conn)
    print("done")

if __name__ == "__main__":
    main()
