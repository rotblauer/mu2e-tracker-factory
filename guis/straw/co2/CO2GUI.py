#   Update: 10/23/18 by Joe Dill
#   Incorporated Credentials Class

#   Update: 10/24/18 by Ben Hiltbrand
#   Added upload to Mu2e Hardware database

import pyautogui
import time
import os
import csv
import sys
from datetime import datetime
from PyQt5.QtCore import QRect, Qt, QTimer, QMetaObject, QCoreApplication
from PyQt5.QtGui import QFont, QPalette, QColor, QBrush
from PyQt5.QtWidgets import (
    QInputDialog,
    QLabel,
    QFrame,
    QStackedWidget,
    QWidget,
    QPushButton,
    QSizePolicy,
    QCheckBox,
    QVBoxLayout,
    QLayout,
    QSpinBox,
    QLineEdit,
    QMainWindow,
    QApplication,
    QComboBox,
    QMessageBox,
)
from pynput.keyboard import Key, Controller
from pathlib import Path
from guis.straw.co2.co2 import Ui_MainWindow  ## edit via Qt Designer

from guis.straw.removestraw import removeStraw
from guis.straw.checkstraw import *
from data.workers.credentials.credentials import Credentials
from guis.common.getresources import GetProjectPaths
from guis.common.save_straw_workers import saveWorkers

pyautogui.FAILSAFE = True  # Move mouse to top left corner to abort script

# to change hitting enter to hitting tab
keyboard = Controller()


class CO2(QMainWindow):
    def __init__(self, paths, webapp=None, parent=None):
        super(CO2, self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.workerDirectory = paths["co2workers"]
        self.palletDirectory = paths["pallets"]
        self.epoxyDirectory = paths["co2epoxy"]
        self.boardPath = paths["board"]
        self.ui.PortalButtons.buttonClicked.connect(self.Change_worker_ID)
        self.stationID = "C-O2"
        self.credentialChecker = Credentials(self.stationID)
        self.Current_workers = [
            self.ui.Current_worker1,
            self.ui.Current_worker2,
            self.ui.Current_worker3,
            self.ui.Current_worker4,
        ]
        self.portals = [
            self.ui.portal1,
            self.ui.portal2,
            self.ui.portal3,
            self.ui.portal4,
        ]
        self.ui.start.clicked.connect(self.initialData)
        self.ui.finishInsertion.clicked.connect(self.timeUp)
        self.ui.finish.clicked.connect(self.finish)
        self.ui.viewButton.clicked.connect(self.editPallet)

        self.ui.palletNumInput.returnPressed.connect(self.scan)
        self.ui.epoxyBatchInput.returnPressed.connect(self.scan)
        self.ui.DP190BatchInput.returnPressed.connect(self.scan)

        self.setTabOrder(self.ui.palletNumInput, self.ui.epoxyBatchInput)
        self.setTabOrder(self.ui.epoxyBatchInput, self.ui.DP190BatchInput)
        self.setTabOrder(self.ui.DP190BatchInput, self.ui.start)

        self.palletID = ""
        self.palletNum = ""
        self.epoxyBatch = ""
        self.DP190Batch = ""
        self.straws = []
        self.sessionWorkers = []

        self.timing = False
        self.startTime = 0

        self.ui.sec_disp.setNumDigits(2)
        self.ui.sec_disp.setSegmentStyle(2)
        self.ui.min_disp.setNumDigits(2)
        self.ui.min_disp.setSegmentStyle(2)
        self.ui.hour_disp.setNumDigits(2)
        self.ui.hour_disp.setSegmentStyle(2)
        self.justLogOut = ""
        saveWorkers(self.workerDirectory, self.Current_workers, self.justLogOut)

    def Change_worker_ID(self, btn):
        label = btn.text()
        portalNum = 0
        if label == "Log In":
            portalNum = int(btn.objectName().strip("portal")) - 1
            Current_worker, ok = QInputDialog.getText(
                self, "Worker Log In", "Scan your worker ID:"
            )
            if not ok:
                return
            self.sessionWorkers.append(Current_worker)
            self.Current_workers[portalNum].setText(Current_worker)
            print("Welcome " + self.Current_workers[portalNum].text() + " :)")
            btn.setText("Log Out")
            # self.ui.tab_widget.setCurrentIndex(1)
        elif label == "Log Out":
            portalNum = int(btn.objectName().strip("portal")) - 1
            self.justLogOut = self.Current_workers[portalNum].text()
            self.sessionWorkers.remove(self.Current_workers[portalNum].text())
            print("Goodbye " + self.Current_workers[portalNum].text() + " :(")
            Current_worker = ""
            self.Current_workers[portalNum].setText(Current_worker)
            btn.setText("Log In")
        saveWorkers(self.workerDirectory, self.Current_workers, self.justLogOut)
        self.justLogOut = ""

    def lockGUI(self):
        self.ui.tab_widget.setTabText(1, "CO2 Endpiece")
        if not self.credentialChecker.checkCredentials(self.sessionWorkers):
            self.ui.tab_widget.setCurrentIndex(0)
            self.ui.tab_widget.setTabText(1, "CO2 Endpiece *Locked*")

    def updateBoard(self):
        status = []
        try:
            with open(self.boardPath / "Progression Status.csv") as readfile:
                data = csv.reader(readfile)
                for row in data:
                    for pallet in row:
                        status.append(pallet)
            status[int(self.palletID[6:]) - 1] == 22
            with open(self.boardPath / "Progression Status.csv", "w") as writefile:
                i = 0
                for pallet in status:
                    writefile.write(pallet)
                    if i != 23:
                        writefile.write(",")
                    i = i + 1
        except IOError:
            print(
                "Could not update board due to board file being accessed concurrently"
            )

    def initialData(self):
        valid = [bool() for i in range(4)]

        # Get inputs
        self.palletNum = self.ui.palletNumInput.text().strip().upper()
        self.epoxyBatch = self.ui.epoxyBatchInput.text().strip().upper()
        self.DP190Batch = self.ui.DP190BatchInput.text().strip().upper()

        # Verify inputs
        valid[1] = self.verifyPalletNumber(self.palletNum)
        valid[2] = self.verifyEpoxyBatch(self.epoxyBatch)
        valid[3] = self.verifyDP190Batch(self.DP190Batch)

        # Verify that pallet number corresponds to a CPALID
        valid[0] = False
        for palletid in os.listdir(self.palletDirectory):
            for pallet in os.listdir(self.palletDirectory / palletid):
                if self.palletNum + ".csv" == pallet:
                    self.palletID = palletid
                    valid[0] = True

        # Update StyleSheets
        if valid[1]:
            self.ui.palletNumInput.setStyleSheet("")
            self.ui.palletNumInput.setText(self.palletNum)
            self.ui.viewButton.setEnabled(True)
        else:
            self.ui.palletNumInput.setStyleSheet("background-color:rgb(255, 0, 0)")

        if valid[2]:
            self.ui.epoxyBatchInput.setStyleSheet("")
            self.ui.epoxyBatchInput.setText(self.epoxyBatch)
        else:
            self.ui.epoxyBatchInput.setStyleSheet("background-color:rgb(255, 0, 0)")

        if valid[3]:
            self.ui.DP190BatchInput.setStyleSheet("")
            self.ui.DP190BatchInput.setText(self.DP190Batch)
        else:
            self.ui.DP190BatchInput.setStyleSheet("background-color:rgb(255, 0, 0)")

        if all(valid):
            try:
                check = Check()
                check.check(self.palletNum, ["prep", "ohms"])
                self.ui.palletNumInput.setDisabled(True)
                self.ui.epoxyBatchInput.setDisabled(True)
                self.ui.DP190BatchInput.setDisabled(True)
                self.ui.start.setDisabled(True)
                self.ui.viewButton.setEnabled(True)
                # self.ui.finishInsertion.setEnabled(True)
                self.stopWatch()
            except StrawFailedError as error:
                QMessageBox.critical(
                    self,
                    "Testing Error",
                    "Unable to test this pallet:\n" + error.message,
                )
                self.editPallet()

    def scan(self):

        # Get current lineEdit
        lineEdit = self.focusWidget()

        string = lineEdit.text().strip().upper()

        verify = {
            self.ui.palletNumInput: self.verifyPalletNumber(string),
            self.ui.epoxyBatchInput: self.verifyEpoxyBatch(string),
            self.ui.DP190BatchInput: self.verifyDP190Batch(string),
        }

        if verify[lineEdit]:
            lineEdit.setText(string)
            lineEdit.setStyleSheet("")
            self.tab()

            if lineEdit == self.ui.palletNumInput:
                self.palletNum = string
                self.ui.viewButton.setEnabled(True)

        else:
            lineEdit.setFocus()
            lineEdit.selectAll()
            lineEdit.setStyleSheet("background-color:rgb(255, 0, 0)")

    def tab(self):
        keyboard.press(Key.tab)

    def verifyPalletNumber(self, pallet_num):
        # Verifies that the given pallet id is of a valid format
        verify = True

        # check that last 4 characters of ID are integers
        if len(pallet_num) == 8:
            verify = pallet_num[
                4:7
            ].isnumeric()  # makes sure last four digits are numbers
        else:
            verify = False  # fails if palled_num

        if not pallet_num.upper().startswith("CPAL"):
            verify = False

        return verify

    def verifyEpoxyBatch(self, eb):

        eb = eb.strip().upper()

        if len(eb) != 13:
            return False
        if not eb.startswith("CO2."):
            return False
        if eb[4:9].isnumeric():
            # Month
            if not int(eb[4:6]) in range(13):
                return False
            # Day
            if not int(eb[6:8]) in range(1, 32):
                return False
            # Year
            if not int(eb[8:10]) in range(
                17, (datetime.now().year - 2000) + 1
            ):  # Max: current year
                return False
        if not eb[10] == ".":
            return False
        if not eb[11:13].isnumeric():
            return False

        return True

    def verifyDP190Batch(self, string):

        string = string.upper().strip()

        if len(string) == 9:
            return string.startswith("DP190.") and string[6:9].isnumeric()
        else:
            return False

    def stopWatch(self):
        self.startTime = time.time()
        self.timing = True

        self.ui.finishInsertion.setEnabled(True)
        self.ui.finish.setDisabled(True)

    def timeUp(self):
        self.timing = False
        self.ui.finishInsertion.setDisabled(True)
        self.ui.finish.setEnabled(True)

    def saveData(self):
        pfile = self.palletDirectory / self.palletID / str(self.palletNum + ".csv")
        if pfile.is_file():
            with open(pfile, "r") as palletFile:
                dummy = csv.reader(palletFile)
                pallet = []
                for line in dummy:
                    pallet.append(line)
                for row in range(len(pallet)):
                    if row == len(pallet) - 1:
                        for entry in range(len(pallet[row])):
                            if entry > 1 and entry < 50:
                                if entry % 2 == 0:
                                    self.straws.append(pallet[row][entry])

            with open(pfile, "a") as palletWrite:
                palletWrite.write("\n")
                palletWrite.write(
                    datetime.now().strftime("%Y-%m-%d_%H:%M") + ","
                )
                palletWrite.write(self.stationID + ",")
                for straw in self.straws:
                    palletWrite.write(straw)
                    palletWrite.write(",")
                    if straw != "":
                        palletWrite.write("P")
                    palletWrite.write(",")
                i = 0
                for worker in self.sessionWorkers:
                    palletWrite.write(worker.lower())
                    if i != len(self.sessionWorkers) - 1:
                        palletWrite.write(",")
                    i = i + 1

        efile = self.epoxyDirectory / str(self.palletNum + ".csv")
        with open(efile, "w+") as ef:
            header = "Timestamp, Pallet ID, Epoxy Batch #, DP190 Batch #, CO2 endpiece insertion time (H:M:S), workers ***NEWLINE: Comments (optional)***\n"
            ef.write(header)
            ef.write(datetime.now().strftime("%Y-%m-%d_%H:%M") + ",")
            ef.write(
                self.palletID + "," + self.epoxyBatch + "," + self.DP190Batch + ","
            )
            ef.write(
                str(self.ui.hour_disp.intValue())
                + ":"
                + str(self.ui.min_disp.intValue())
                + ":"
                + str(self.ui.sec_disp.intValue())
                + ","
            )
            i = 0
            for worker in self.sessionWorkers:
                ef.write(worker)
                if i != len(self.sessionWorkers) - 1:
                    ef.write(",")
                i = i + 1
            if self.ui.commentBox.document().toPlainText() != "":
                ef.write("\n" + self.ui.commentBox.document().toPlainText())

        QMessageBox.about(self, "Save", "Data saved successfully!")

    def resetGUI(self):
        self.palletID = ""
        self.palletNum = ""
        self.epoxyBatch = ""
        self.DP190Batch = ""
        self.straws = []
        self.ui.palletNumInput.setEnabled(True)
        self.ui.epoxyBatchInput.setEnabled(True)
        self.ui.DP190BatchInput.setEnabled(True)
        self.ui.palletNumInput.setText("")
        self.ui.epoxyBatchInput.setText("")
        self.ui.DP190BatchInput.setText("")
        self.ui.commentBox.document().setPlainText("")
        self.ui.start.setEnabled(True)
        self.ui.hour_disp.display(0)
        self.ui.min_disp.display(0)
        self.ui.sec_disp.display(0)
        self.ui.viewButton.setDisabled(True)
        self.ui.finishInsertion.setDisabled(True)
        self.ui.finish.setDisabled(True)
        """for i in range(len(self.Current_workers)):
            if self.Current_workers[i].text() != '':
                self.Change_worker_ID(self.portals[i])
        self.sessionWorkers = []"""

    def editPallet(self):
        rem = removeStraw(self.sessionWorkers)
        rem.palletDirectory = self.palletDirectory
        CPAL, lastTask, straws, passfail = rem.getPallet(self.palletNum)
        rem.displayPallet(CPAL, lastTask, straws, passfail)
        rem.exec_()

    def finish(self):
        self.saveData()
        self.resetGUI()

    def closeEvent(self, event):
        event.accept()
        sys.exit(0)

    def main(self, app):
        while True:
            if self.timing:
                running = time.time() - self.startTime
                self.ui.hour_disp.display(int(running / 3600))
                self.ui.min_disp.display(int(running / 60) % 60)
                self.ui.sec_disp.display(int(running) % 60)

            self.lockGUI()
            time.sleep(0.01)
            app.processEvents()


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)
    sys.exit()


def run():
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    paths = GetProjectPaths()
    ctr = CO2(paths)
    ctr.show()
    ctr.main(app)
    app.exec_()


if __name__ == "__main__":
    run()
