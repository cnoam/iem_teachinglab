import logging

class MoodleFileParser:
    """this class has helper methods to parse files created by Moodle
    The parsed data can then be used by external script
    :author: Noam Cohen
    """

    def __init__(self):
        pass

    @classmethod
    def parse_moodle_csv(cls, filename: str):
        """
        read a CSV file containing Group assignment in Moodle.
        Currently limited to 3 members in each group.
        :return: dict { id:integer -> [user_email] }
        """
        import csv
        out = {}
        rowcount = 0

        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                user3 = ''

                if rowcount == 0:
                    if row[0] != 'Group ID':
                        raise Exception('unexpected CSV format. First line MUST start with "Group ID"')
                    col_names = row
                    index_email1 = col_names.index('Member 1 Email')
                    index_email2 = col_names.index('Member 2 Email')
                    index_email3 =  col_names.index('Member 3 Email')
                    rowcount = 1
                    continue  # skip header
                if len(row) == 0:
                    continue
                if len(row) >= 23:
                    user3 = row[index_email3]
                rowcount += 1
                if len(row) < index_email1:
                    logging.error(f"skipping invalid row in CSV file: {row}")
                    continue
                out[rowcount] = []
                user1 = row[index_email1]
                if len(row) > index_email1+1:
                    user2 = row[index_email2]
                else: user2 = ''
                if user1 != '': out[rowcount].append(user1)
                if user2 != '': out[rowcount].append(user2)
                if user3 != '': out[rowcount].append(user3)
        return out


if __name__ == "__main__":
    out = MoodleFileParser.parse_moodle_csv('/home/cnoam/Downloads/Groupself-selection_00094290.01_2024-01-14.csv')