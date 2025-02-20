#
#   Author:             Cole Kampa, Jacob Christy
#   Email:         <kampa041@umn.edu> <chri3448@umn.edu>
#   Institution: University of Minnesota
#   Project:              Mu2e
#   Date:				6/11/18
#
#   Description:
#   A Python 3 script located in Lazer_Adjust folder that edits the .ecp file used for the second half of the straw cutting
#   on the laser. This adjusts the location of each cut in the Y direction to account for length
#   expansion and contraction due to varying temperature and humidity. The temp and humidity are entered
#   in the GLOBAL VARIABLES section (but will eventually be pulled from the website).
#   .csv file to load in with format: Position,   StrawLength(in), Base_x, Base_y, Top_x(pixels),  Top_y(pixels)
#                                     (0,4,2,6,etc)                  (in LaserCut to adjust)  (location on laptop to start click)
#   Pixel locations for .csv file can be determined using mouseLoc.py in MouseLocation
#   NOTE: The straw with the largest y value is the shortest straw
#
#   Modules: pyautogui, PyQt5
#
#
#   Updated to new laser cut files, as well as adding in pallet check before cutting
#   -- Ben Hiltbrand 12/12/18

import pyautogui
import time
import os
import csv
import sys
import threading
import win32gui
import win32con

from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QRect, Qt, QTimer, QMetaObject, QCoreApplication, pyqtSignal
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
from guis.straw.laser.Laser import Ui_MainWindow  ## edit via Qt Designer

pyautogui.FAILSAFE = True  # Move mouse to top left corner to abort script

from data.workers.credentials.credentials import Credentials
from guis.straw.removestraw import removeStraw
from guis.straw.checkstraw import *
from guis.common.getresources import GetProjectPaths
from guis.common.save_straw_workers import saveWorkers


##**GLOBAL VARIABLES**##
# TEMP = 72.0 #current temp  ##ONLY FOR TESTING
# HUMID = 25.0 #current humidity   ##ONLY FOR TESTING

TEMP_INIT = 68.0  # temp for original setting
HUMID_INIT = 0.0  # humidity for original setting

"""CSV_FILE_04 = 'LaserInfo0,4.csv'
LASERCUT_FILE_04 = 'Cut 2 for 0,4 - version 3.ecp'

CSV_FILE_26 = 'LaserInfo2,6.csv'
LASERCUT_FILE_26 = 'Cut 2 for 2,6 - version 3.ecp'"""

X_SIZE = 3  # set pixel amount to adjust to right and down
Y_SIZE = 7

C1 = 0.0000094  # Temperature correction
C2 = 0.0000096  # Humidity coefficient


class cutMenu(QMainWindow):
    LockGUI = pyqtSignal(bool)

    def __init__(self, paths, webapp=None, parent=None):
        super(cutMenu, self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.PortalButtons.buttonClicked.connect(self.Change_worker_ID)
        self.ui.viewButton.clicked.connect(self.editPallet)
        self.workerDirectory = paths["laserworkers"]
        self.palletDirectory = paths["pallets"]
        self.boardPath = paths["board"]
        self.laserDirectory = paths["laserdata"]
        self.palletID = ""
        self.palletNum = ""
        self.cutType = ""
        self.cutTemperature = ""
        self.cutHumidity = ""
        self.cutLengths = []
        self.sessionWorkers = []
        self.straws = []
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
        self.justLogOut = ""
        saveWorkers(self.workerDirectory, self.Current_workers, self.justLogOut)
        self.scanEntry = ""
        self.step = 0
        self.ui.instructions.setFocus()
        self.ui.commentBox.setPlaceholderText(
            "After adding a comment, click on the instruction above to continue."
        )
        self.humidValues = [10, 25, 40, 55]
        self.stationID = "lasr"
        self.credentialChecker = Credentials(self.stationID)

        self.LockGUI.connect(self.lockGUI)
        self.lockGUI(False)

        self.getTempHumid()

        thread = threading.Thread(target=self.main, args=())
        thread.daemon = True
        thread.start()

    """def checkPreviousStep(self, CPAL, previousStep):
        for palletid in os.listdir(self.palletDirectory):
            for pallet in os.listdir(self.palletDirectory / palletid):
                if CPAL + '.csv' == pallet:
                    pfile = self.palletDirectory / palletid / pallet
                    with open(pfile, 'r') as file:
                        dummy = csv.reader(file)
                        history = []
                        for line in dummy:
                            if line != []:
                                history.append(line)
                        for line in history:
                            if line[1] == previousStep:
                                Pass = []
                                for entry in range(len(line)):
                                    if entry > 1 and entry < 50:
                                        if entry%2 == 1:
                                            if line[entry - 1] != '_______':
                                                if line[entry] == 'P':
                                                    Pass.append(True)
                                                else:
                                                    Pass.append(False)
                                if all(Pass):
                                    return True
        return False"""

    def keyPressEvent(self, qKeyEvent):
        if qKeyEvent.key() == Qt.Key_F:
            self.scanEntry = "F"
        if qKeyEvent.key() == Qt.Key_I and self.scanEntry == "F":
            self.scanEntry = self.scanEntry + "I"
        if qKeyEvent.key() == Qt.Key_R and self.scanEntry == "FI":
            self.scanEntry = self.scanEntry + "R"
        if qKeyEvent.key() == Qt.Key_S and self.scanEntry == "FIR":
            self.scanEntry = self.scanEntry + "S"
        if qKeyEvent.key() == Qt.Key_T and self.scanEntry == "FIRS":
            self.scanEntry = self.scanEntry + "T"
        if qKeyEvent.key() == Qt.Key_Return and self.scanEntry == "FIRST":
            self.firstCut()
        if (
            qKeyEvent.key() == Qt.Key_S
            and self.scanEntry != "FIR"
            and self.scanEntry != "FIRS"
            and self.scanEntry != "FINI"
        ):
            self.scanEntry = "S"
        if qKeyEvent.key() == Qt.Key_E and self.scanEntry == "S":
            self.scanEntry = self.scanEntry + "E"
        if qKeyEvent.key() == Qt.Key_C and self.scanEntry == "SE":
            self.scanEntry = self.scanEntry + "C"
        if qKeyEvent.key() == Qt.Key_O and self.scanEntry == "SEC":
            self.scanEntry = self.scanEntry + "O"
        if qKeyEvent.key() == Qt.Key_N and self.scanEntry == "SECO":
            self.scanEntry = self.scanEntry + "N"
        if qKeyEvent.key() == Qt.Key_D and self.scanEntry == "SECON":
            self.scanEntry = self.scanEntry + "D"
        if qKeyEvent.key() == Qt.Key_Return and self.scanEntry == "SECOND":
            self.scanEntry = ""
            self.chooseCut()
        if qKeyEvent.key() == Qt.Key_N and self.scanEntry == "FI":
            self.scanEntry = self.scanEntry + "N"
        if qKeyEvent.key() == Qt.Key_I and self.scanEntry == "FIN":
            self.scanEntry = self.scanEntry + "I"
        if qKeyEvent.key() == Qt.Key_S and self.scanEntry == "FINI":
            self.scanEntry = self.scanEntry + "S"
        if qKeyEvent.key() == Qt.Key_H and self.scanEntry == "FINIS":
            self.scanEntry = self.scanEntry + "H"
        if qKeyEvent.key() == Qt.Key_Return and self.scanEntry == "FINISH":
            self.scanEntry = ""
            self.saveData()

    ##**FUNCTIONS**##
    # Load Data from .csv file into 2d list
    def loadData(self, filename, directory):
        lengths = []
        x_i = []
        y_i = []
        x_start = []
        y_start = []
        print(str(directory / filename))
        with open(directory / filename) as csvf:
            csvReader = csv.reader(csvf)
            firstline = True
            for row in csvReader:
                if firstline:
                    firstline = False
                    continue
                lengths.append(float(row[1]))
                x_i.append(float(row[2]))
                y_i.append(float(row[3]))
                x_start.append(float(row[4]))
                y_start.append(float(row[5]))
        return lengths, x_i, y_i, x_start, y_start

    # Open LaserCut & .ecp File
    def openFile(self, filename, directory):
        """print("check1")
        toplist = []
        winlist = []
        def enum_callback(hwnd, results):
            winlist.append((hwnd, win32gui.GetWindowText(hwnd)))
        win32gui.EnumWindows(enum_callback, toplist)
        for (num, title) in winlist:
            if ("firefox" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
            if ("visual" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
            if ("mainwindow" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
            if ("python" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
            if ("py" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
            if ("file" in title.lower()):
                win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        print("check2")"""
        os.system("start C:\\LaserCut53\\LaserCut53.exe")
        time.sleep(2)
        pyautogui.click(948, 595)
        pyautogui.click(1058, 482)
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "o")
        time.sleep(1)
        print("Trying to open '{}' from directory: '{}'".format(str(filename), str(directory)))
        pyautogui.typewrite(str(directory) + "\\" + str(filename))
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(1)
        pyautogui.hotkey("shift", "f4")  # zoom to table
        time.sleep(0.5)
        print("File was successfully opened")

    # Obtain current temperature and humidity
    # First try to get from file, else manual entry
    def getTempHumid(self):
        temperature = humidity = None
        temp_ok = humid_ok = True
        # First, search local data dir for today's temp/humidity file.
        # If that doesn't work get it manually.
        try:
            directory = GetProjectPaths()["temp_humid_data"] / "464_main"
            D = os.listdir(directory)
            filename = ""
            for entry in D:
                if entry.startswith("464_" + datetime.now().strftime("%Y-%m-%d")):
                    filename = entry

            print("Attempting to read temp/humid from", str(directory / filename))
            with open(directory / filename) as f:
                # skip null bytes, which often appear if we seized the file
                # while it was still open.
                data = csv.reader(x.replace("\0", "") for x in f)
                rows = list(data)
                temperature = float(rows[-1][1])
                humidity = float(rows[-1][2])
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Temperature and Humidity File Not Found",
                "Merge down to get the latest file. If you did that and are "
                "still receiving this message, the sensor may not be working "
                "properly. In any case, just enter the temp/humid manually "
                "now.",
            )
            temperature, temp_ok = QInputDialog.getText(
                self, "Temperature", "Enter room temperature"
            )
            humidity, humid_ok = QInputDialog.getText(
                self, "Humidity", "Enter room humidity"
            )

        print("Using Temperature:", temperature)
        print("Using Humidity:", humidity)

        # Check for valid temp and humidity
        try:
            int(temperature)
            int(humidity)
            assert temp_ok
            assert humid_ok
        except:
            QMessageBox.critical(
                self,
                "Bad Temperature and/or Humidity.",
                "Continuing without temp and humidity.",
            )

        self.temperature = float(temperature)
        self.humidity = float(humidity)

    def loadLaser(self):
        pyautogui.click(1868, 582)
        time.sleep(1)
        pyautogui.click(894, 634)
        time.sleep(1)
        pyautogui.click(962, 606)
        time.sleep(2)
        pyautogui.click(1110, 382)
        time.sleep(1)
        pyautogui.click(1761, 322)
        time.sleep(4)
        pyautogui.click(1712, 494)
        time.sleep(0.5)

    def getPalletNum(self):
        pallet, ok = QInputDialog().getText(
            self, "Pallet Number", "Please scan the Pallet Number", text="CPAL####"
        )

        pallet = pallet.strip().upper()  # remove spaces and put in CAPS

        if ok:
            if self.verifyPalletNum(pallet):
                self.palletNum = pallet
                for palletid in os.listdir(self.palletDirectory):
                    for pal in os.listdir(self.palletDirectory / palletid):
                        if self.palletNum + ".csv" == pal:
                            self.palletID = palletid
            else:
                self.getPalletNum()

    def verifyPalletNum(self, pallet_num):
        # Verifies that the given pallet id is of a valid format
        verify = True

        # check that last 4 characters of ID are integers
        if len(pallet_num) == 8:
            verify = pallet_num[
                4:7
            ].isnumeric()  # makes sure last four digits are numbers
        else:
            verify = False

        if not pallet_num.upper().startswith("CPAL"):
            verify = False

        return verify

    def initializePallet(self):

        # Obtain pallet number
        if not self.palletNum:
            self.getPalletNum()

        if self.palletNum:
            # Display Pallet Info Window
            #   - Hint that user remove all failed straws
            #   - Calls interpretEditPallet() to
            #     obtain most recent pallet info
            self.ui.pallet.setText(self.palletNum)
            self.ui.viewButton.setEnabled(True)
            rem = removeStraw(self.sessionWorkers)
            rem.palletDirectory = self.palletDirectory
            rem.sessionWorkers = self.sessionWorkers
            CPAL, lastTask, straws, passfail = rem.getPallet(self.palletNum)
            self.interpretEditPallet(CPAL, lastTask, straws, passfail)

    def editPallet(self):

        rem = removeStraw(self.sessionWorkers)
        rem.palletDirectory = self.palletDirectory
        rem.sessionWorkers = self.sessionWorkers
        CPAL, lastTask, straws, passfail = rem.getPallet(self.palletNum)
        rem.displayPallet(CPAL, lastTask, straws, passfail)
        rem.exec_()

        CPAL, lastTask, straws, passfail = rem.getPallet(
            self.palletNum
        )  # Run again incase changes were made (straws removed, moved, etc...)
        # After executing
        self.interpretEditPallet(CPAL, lastTask, straws, passfail)

    def interpretEditPallet(self, CPAL, lastTask, straws, passfail):

        self.palletInfoVerified = (
            True  # Initially assume True, can only be switched to False
        )

        if lastTask != "leak":
            self.palletInfoVerified = False
            # self.setStatus(self.palletInfoVerified)
            # Error Message
            QMessageBox.about(
                self,
                "Remove Straws",
                "Please verify that this pallet has been leak tested.",
            )
            return

        # Check for failed straws
        remove_straws = []
        for i in range(24):
            if (
                passfail[i] == "Fail"
                or passfail[i] == "Incomplete"
                and straws[i] != "Empty"
            ):
                remove_straws.append(straws[i])

        # self.setStatus((len(remove_straws) == 0))

        # No failed straws are present
        if len(remove_straws) == 0:
            return
        # If failed straws are present, instruct user to remove them and run editPallet() (which will call this function again)
        else:
            self.palletInfoVerified = False

            instructions = "The following straws failed and need to be removed before laser cutting:"
            for strawID in remove_straws:
                instructions += "\n" + strawID
            buttonreply = QMessageBox.question(
                self,
                "Remove Straws",
                instructions,
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )

            if buttonreply != QMessageBox.Cancel:
                self.editPallet()

    def firstCut(self):
        filename = "Cut 1.ecp"
        directory = str(GetProjectPaths()["lasercutfiles"] / "Cut_1")
        self.openFile(filename, directory)
        self.changeSettings()
        self.loadLaser()
        self.step = 1
        self.ui.instructions.setText(
            "After the laser is done with the first cut, slowly slide the pallet to its second cut position. Once the pallet is in place, scan the SECOND bardcode. The second cut will begin immediately after scanning SECOND.\n\nDo not touch the mouse or keyboard for 60 seconds after pressing Second Cut."
        )

    def chooseCut(self):
        if self.step != 1:
            reply = QMessageBox.question(
                self,
                "First Cut",
                "Have you done the first cut?",
                QMessageBox.Yes,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.step = 1
            else:
                return
        parity = int(self.palletNum[4:]) % 2
        if parity == 0:
            self.zerofour()
        if parity == 1:
            self.twosix()
        self.step = 2

    def zerofour(self):
        self.cutType = "(0-4)"
        # TEMP, HUMID = self.loadTH()
        TEMP = self.temperature
        HUMID = self.humidity
        self.cutTemperature = str(TEMP)
        self.cutHumidity = str(HUMID)
        TEMP = (TEMP * 9 / 5) + 32
        diff = []
        for v in self.humidValues:
            diff.append((HUMID - v) * (HUMID - v))
        index = diff.index(min(diff))
        humidString = str(self.humidValues[index])
        directory = GetProjectPaths()["lasercutfiles"] / str("Cut2-RH" + humidString)
        filename = "Cut 2 for 0,4 - RH" + humidString + ".ecp"
        print(filename)

        with open(directory / str("LaserInfo0,4RH" + humidString + ".csv"), "r") as list:
            reader = csv.reader(list)

            for row in reader:
                self.cutLengths.append(row[1])

        print("Second cut opening from", str(directory))
        self.openFile(filename, directory)

        # if the y value increases (shorter straw length), start from top, else start from bottom
        # this avoids autogui from accidentally selecting the wrong cut or multiple cuts

        """if ((TEMP - TEMP_INIT)*C1 + (HUMID - HUMID_INIT)*C2) > 0:
            for i in range(len(x_i)):
                length = self.changeLoc(x_start[i], y_start[i], x_i[i], y_i[i], lengths[i],TEMP,HUMID)
                self.cutLengths.append(length)
        else:
            for i in reversed(range(len(x_i))):
                length = self.changeLoc(x_start[i], y_start[i], x_i[i], y_i[i], lengths[i],TEMP,HUMID)
                self.cutLengths.append(length)
            self.cutLengths = list(reversed(self.cutLengths))"""
        self.changeSettings()
        self.loadLaser()
        self.ui.instructions.setText(
            "Remove the straw samples from the pallet and insert them into a new film canister. Label the canister with the Pallet # and insert it into the canister storage drawer.\n\nRemove and discard of the scrap ends of the straws and place the pallet on rack A. After this, scan FINISH."
        )

    def twosix(self):
        self.cutType = "(2-6)"
        # TEMP, HUMID = self.loadTH()
        TEMP = self.temperature
        HUMID = self.humidity
        self.cutTemperature = str(TEMP)
        self.cutHumidity = str(HUMID)
        TEMP = (TEMP * 9 / 5) + 32
        diff = []
        for v in self.humidValues:
            diff.append((HUMID - v) * (HUMID - v))
        index = diff.index(min(diff))
        humidString = str(self.humidValues[index])
        directory = GetProjectPaths()["lasercutfiles"] / str("Cut2-RH" + humidString)
        filename = "Cut 2 for 2,6 - RH" + humidString + ".ecp"
        print(filename)

        with open(directory / str("LaserInfo2,6RH" + humidString + ".csv"), "r") as list:
            reader = csv.reader(list)

            for row in reader:
                self.cutLengths.append(row[1])

        print("Second cut opening from", str(directory))
        self.openFile(filename, directory)

        # if the y value increases (shorter straw length), start from top, else start from bottom
        # this avoids autogui from accidentally selecting the wrong cut or multiple cuts
        """if ((TEMP - TEMP_INIT)*C1 + (HUMID - HUMID_INIT)*C2) > 0:
            for i in range(len(x_i)):
                length = self.changeLoc(x_start[i], y_start[i], x_i[i], y_i[i], lengths[i],TEMP,HUMID)
                self.cutLengths.append(length)
        else:
            for i in reversed(range(len(x_i))):
                length = self.changeLoc(x_start[i], y_start[i], x_i[i], y_i[i], lengths[i],TEMP,HUMID)
                self.cutLengths.append(length)
            self.cutLengths = list(reversed(self.cutLengths))"""

        self.changeSettings()
        self.loadLaser()
        self.ui.instructions.setText(
            "Remove the straw samples from the pallet and insert them into a new film canister. Label the canister with the Pallet # and insert it into the canister storage drawer.\n\nRemove and discard of the scrap ends of the straws and place the pallet on rack A. After this, scan FINISH."
        )

    def changeSettings(self):
        pyautogui.doubleClick(1852, 107)
        time.sleep(0.5)
        pyautogui.doubleClick(912, 482)
        time.sleep(0.5)
        pyautogui.typewrite("30")
        time.sleep(0.5)
        pyautogui.doubleClick(1058, 482)
        time.sleep(0.5)
        pyautogui.typewrite("100")
        time.sleep(0.5)
        pyautogui.click(912, 574)
        time.sleep(0.5)
        print("Settings have been changed")

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
            # self.ui.tabWidget.setCurrentIndex(1)
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

    def checkCredentials(self):
        return self.credentialChecker.checkCredentials(self.sessionWorkers)

    def lockGUI(self, credentials):
        if credentials:
            self.ui.tabWidget.setTabText(1, "Laser Cut")
            self.ui.tabWidget.setTabEnabled(1, True)
            self.ui.tabWidget.setCurrentIndex(1)
            self.resetGUI()
        else:
            self.ui.tabWidget.setTabText(1, "Laser Cut *Locked*")
            self.ui.tabWidget.setTabEnabled(1, False)

    def updateBoard(self):
        status = []
        try:
            psfile = self.boardPath / "Progression Status.csv"
            with open(psfile, "r") as readfile:
                data = csv.reader(readfile)
                for row in data:
                    for pallet in row:
                        status.append(pallet)
            status[int(self.palletID[6:]) - 1] = 65
            with open(psfile, "w") as writefile:
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

    def saveData(self):
        if self.step != 2:
            return
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
                palletWrite.write(datetime.now().strftime("%Y-%m-%d_%H:%M") + ",")
                palletWrite.write("lasr,")
                for straw in self.straws:
                    palletWrite.write(straw)
                    palletWrite.write(",")
                    if straw != "":
                        palletWrite.write("P")
                    palletWrite.write(",")
                i = 0
                palletWrite.write(",".join(self.sessionWorkers))

            with open(pfile, "a") as palletWrite:
                palletWrite.write("\n")
                palletWrite.write(datetime.now().strftime("%Y-%m-%d_%H:%M") + ",")
                palletWrite.write("leng,")
                for straw in self.straws:
                    palletWrite.write(straw)
                    palletWrite.write(",")
                    if straw != "":
                        palletWrite.write("P")
                    palletWrite.write(",")
                i = 0
                palletWrite.write(",".join(self.sessionWorkers))

        lfile = self.laserDirectory / str(self.palletNum + ".csv")
        with open(lfile, "w+") as file:
            header = "Timestamp, Pallet ID, Cut Type (0-4) or (2-6), Cut Temperature [C], Cut Humidity, workers ***NEWLINE***: Straw Names (24) ***NEWLINE***: Cut Lengths mm (24) ***NEWLINE***: Comments (optional)***\n"
            file.write(header)
            file.write(datetime.now().strftime("%Y-%m-%d_%H:%M") + ",")
            file.write(self.palletID + ",")
            file.write(self.cutType + ",")
            file.write(self.cutTemperature + ",")
            file.write(self.cutHumidity + ",")
            i = 0
            for worker in self.sessionWorkers:
                file.write(worker)
                if i != len(self.sessionWorkers) - 1:
                    file.write(",")
                i = i + 1
            file.write("\n")
            i = 0
            for straw in self.straws:
                file.write(straw)
                if i != len(self.straws) - 1:
                    file.write(",")
                i = i + 1
            file.write("\n")
            i = 0
            for cut in reversed(self.cutLengths):
                file.write(cut)
                if i != len(self.cutLengths) - 1:
                    file.write(",")
                i = i + 1
            if self.ui.commentBox.document().toPlainText() != "":
                file.write("\n" + self.ui.commentBox.document().toPlainText())
        # self.updateBoard()
        # self.uploadData()
        self.resetGUI()

    def editPallet(self):
        rem = removeStraw(self.sessionWorkers)
        rem.palletDirectory = self.palletDirectory
        rem.sessionWorkers = self.sessionWorkers
        CPAL, lastTask, straws, passfail = rem.getPallet(self.palletNum)
        rem.displayPallet(CPAL, lastTask, straws, passfail)
        rem.exec_()
        CPAL, lastTask, straws, passfail = rem.getPallet(
            self.palletNum
        )  # Run again incase changes were made (straws removed, moved, etc...)
        self.interpretEditPallet(CPAL, lastTask, straws, passfail)

    def resetGUI(self):
        self.palletID = ""
        self.palletNum = ""
        self.cutType = ""
        self.cutTemperature = ""
        self.cutHumidity = ""
        self.cutLengths = []
        self.straws = []
        self.ui.viewButton.setDisabled(True)
        self.ui.pallet.setText("")
        self.ui.palletNumInput.setStyleSheet(
            "background : rgb(255, 255, 255);\nborder-style : solid;\nborder-color: rgb(170, 255, 255);\nborder-width : 2px;"
        )
        self.ui.commentBox.document().setPlainText("")
        self.step = 0
        self.ui.instructions.setText(
            "Once the pallet is properly alligned on the cutting table, "
            "scan the pallet number with format CPAL####."
            "\n\nNext scan the FIRST barcode to initiate the first cut. "
            "If this information is correct, the first cut will begin "
            "immediately."
            "\n\nDo not touch the mouse or keyboard for 60 seconds after "
            "scanning FIRST."
        )
        self.ui.instructions.setFocus()
        self.initializePallet()

    def main(self):
        changed = False
        while True:
            credentials = self.checkCredentials()

            if (credentials and not changed) or (not credentials and changed):
                self.LockGUI.emit(credentials)
                changed = not changed

            time.sleep(0.1)

    def closeEvent(self, event):
        event.accept()
        sys.exit(0)


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)
    sys.exit()


def run():
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    paths = GetProjectPaths()
    ctr = cutMenu(paths)
    ctr.show()
    app.exec_()


if __name__ == "__main__":
    run()


def closeWindows():
    toplist = []
    winlist = []

    def enum_callback(hwnd, results):
        winlist.append((hwnd, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(enum_callback, toplist)
    for (num, title) in winlist:
        if "firefox" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        if "visual" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        if "mainwindow" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        if "python" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        if "py" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
        if "file" in title.lower():
            win32gui.ShowWindow(num, win32con.SW_MINIMIZE)
