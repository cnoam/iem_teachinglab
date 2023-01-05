
class MoodleFileParser:
    """this class has helper methods to parse files created by Moodle
    The parsed data can then be used by external script
    :author: Noam Cohen
    """

    def __init__(self):
        pass

    def parse_moodle_csv(filename: str):
        """
        read a CSV file containing Group assignment in Moodle.
        Currently limited to 2 members in each group.
        :return:
        """
        import csv
        out = {}
        rowcount = 0
        index_email1 = 12
        index_email2 = 17
        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                rowcount += 1
                if rowcount == 1:
                    continue  # skip header
                if len(row) == 0:
                    continue
                if len(row) > 18:
                    raise RuntimeError("Unexpected CSV format. Too many fields")

                out[rowcount] = []
                user1 = row[index_email1]
                user2 = row[index_email2]
                if user1 != '': out[rowcount].append(user1)
                if user2 != '': out[rowcount].append(user2)
        return out




def get_emails(filename: str):
    """ read email addresses from CSV file without a header. One email per line"""
    import csv
    out = []
    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if len(row) == 0:
                continue
            out.append(row[0])
    return out


if __name__ == "__main__":

    MoodleFileParser.parse_moodle_csv('/home/cnoam/Desktop/94290w2022.csv')