from time import perf_counter

from django.core.management.base import BaseCommand

from sagui.utils import reference_data as reference_data_utils


class Command(BaseCommand):
    help = '''
    Get a very plain CSV data provided by Adrien and publish it into the DB
    '''
    def add_arguments(self, parser):
        parser.add_argument('-p', '--path',
                            help='path to the folder containing the CSV files')

    def handle(self, *args, **kwargs):
        tic = perf_counter()

        filepath = kwargs['path']

        reference_data_utils.import_csv(filepath)

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {}'.format(tac - tic)))

