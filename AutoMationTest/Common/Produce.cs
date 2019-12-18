using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;
using System.Windows.Forms;
using AutoMationTest.UI;
using System.Threading;
using AutoMationTest.Function;
using AutoMationTest.Robots;

namespace AutoMationTest.Common
{
    public class Produce
    {

        private static Mutex mutex1 = new Mutex(false);
        private static Mutex mutex2 = new Mutex(false);
        private static Mutex mutex3 = new Mutex(false);
        private static Mutex mutex4 = new Mutex(false);

        public static int LianxuWarningCount = 3;
        public static bool WarningStopUse = false;
        public static Robot Epson;
        public static string[] pcruntimeset = "99,23".Split(',');

        public static YuLanForm yulans = new YuLanForm();
        public static bool bLoginOK = false;//手動操作是否登錄成功。
        public static string LoginName = "";
        public static string LoginID = "";
        public static int UserLevel = 0;
        public static string UserJob = "";
        public static int LoginTimeOut = 10;
        public static string MainWarning = "";
        public static string RobotWarning = "";
        public static bool QuxiaoWarning = false;
        public static bool[] RobotDoneOver_ByStation;
        public static bool GoldenNG_SwitchMode = false;
        public static bool bNotUseSafeDoor = false ;

        public static bool bControlFixture = false;
        public static string RobotGetSN = "";

        //public static GoldenSampleForm GoldenSettingForm = new GoldenSampleForm();

        public static bool bNeedBaoJing = false;
        public static bool[] bShowATS;
        public static bool[] bTestGolden;

        public static bool bManualChangeStatus;//是否已在手動操作。
        public static double YeildRate = 0;//總良率。

        public static bool bAlreadyGetStationInfo = false;

        public static ATSQueue QUEUE;
        public static _robotpoint RobotPoint = new _robotpoint();
        //public static QueueShow showQueue;

        public struct _robotpoint
        {
            public Hashtable Pick;
            public Hashtable Put;
            public Hashtable Laser;
        }

        public struct _grr
        {
            public int LoopCount;
            public int DUTCount;
            public int TestCount;
        }

        public static _grr GRR = new _grr();

        public struct _haocai
        {
            public int Count;
            public Hashtable Name;
            public Hashtable HType;
            public Hashtable Spec;
            public Hashtable UseCount;
            public Hashtable HistoryUseCount;

        }

        public static _haocai HaoCai = new _haocai();

        public struct _stationinfostruct
        {
            public int Count;
            public string[] NameAll;
            public Hashtable Name;
            public Hashtable Index;
            public Hashtable TimeOut;
            public Hashtable NumberList;

            public Hashtable GoldenTestTime;
            public Hashtable GoldenTestTimeOnce;
            public Hashtable GoldenLastTimeRecord;
            public int GoldenIOindex;
            public Hashtable GroupPriority;
            public Hashtable FixturePriority;
            public Hashtable Group;
            public Hashtable Buffer;
            public Hashtable WaitTestBuffer;
            public Hashtable ReTestBuffer;
            public Hashtable TouLiao;
            public Hashtable TouLiaoIO;
            public Hashtable TouLiaoCount;
            public Hashtable PassZone;
            public Hashtable PassZoneIO;
            public Hashtable PassZoneCount;
            public Hashtable NGZone;
            public Hashtable NGZoneIO;
            public Hashtable NGZoneCount;
            public string TXPower;
            public string GRR;
            public string TanZhenStation;
            public int TanZhenIOindex;
            public Hashtable TanZhenLastTestTime;
        }

        public static _stationinfostruct Station = new _stationinfostruct();

        public enum RobotCMD
        {
            Null,
            PASS,
            NG,
            Put,
            //Pick,
            ChouJian,
            Retest

        }

        private static double _TotalDUT = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "Warning", "0"));
        public static double TotalDUTCount
        {
            get
            {
                return _TotalDUT;
            }
            set
            {
                mutex1.WaitOne();
                _TotalDUT = value;

                mutex1.ReleaseMutex();
            }
        }

        private static double _NGDUT = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "NG", "0"));
        public static double NGDUTCount
        {
            get
            {
                return _NGDUT;
            }
            set
            {
                mutex2.WaitOne();
                _NGDUT = value;
                TotalDUTCount = PassDUTCount + _NGDUT + WarningDUTCount;
                //INI.WriteINI(Application.StartupPath + "\\Data","Test", "All", "NG", "");
                if (_NGDUT == 0)
                {
                    YeildRate = 100;
                }
                else
                {
                    YeildRate = Math.Round(PassDUTCount / (PassDUTCount + _NGDUT) * 100, 2);
                }

                mutex2.ReleaseMutex();
            }
        }

        private static double _PassDUT = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "Pass", "0"));
        public static double PassDUTCount
        {
            get
            {
                return _PassDUT;
            }
            set
            {
                mutex3.WaitOne();
                _PassDUT = value;
                TotalDUTCount = _PassDUT + NGDUTCount + WarningDUTCount;
                if (NGDUTCount == 0)
                {
                    YeildRate = 100;
                }
                else
                {
                    YeildRate = Math.Round(_PassDUT / (_PassDUT + NGDUTCount) * 100, 2);
                }

                mutex3.ReleaseMutex();
            }
        }

        private static double _warnDUT = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "Warning", "0"));
        public static double WarningDUTCount
        {
            get
            {
                return _warnDUT;
            }
            set
            {
                mutex4.WaitOne();
                _warnDUT = value;
                TotalDUTCount = PassDUTCount + NGDUTCount + _warnDUT;

                mutex4.ReleaseMutex();
            }
        }

        private static void AddPoint(string name)
        {
            string itemname1 = name + "_Pick";
            string readvalue1 = INI.ReadINI(Application.StartupPath + "\\Data", "Point", "Pick", itemname1, "0,0,0,0,0,0");
            RobotPoint.Pick.Add(itemname1, readvalue1);

            string itemname2 = name + "_Put";
            string readvalue2 = INI.ReadINI(Application.StartupPath + "\\Data", "Point", "Put", itemname2, "0,0,0,0,0,0");
            RobotPoint.Put.Add(itemname2, readvalue2);

            string itemname3 = name + "_Laser";
            string readvalue3 = INI.ReadINI(Application.StartupPath + "\\Data", "Point", "Laser", itemname3, "0,0,0,0,0,0");
            RobotPoint.Laser.Add(itemname3, readvalue3);
        }

        private static string ReadPoint(string name)
        {
            string[] split = name.Split('_');
            string pvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", split[split.Length - 1], name, "0,0,0,0,0,0");
            return pvalue;
        }



        public static void SetPoint(string name, string pvalue)
        {
            string[] split = name.Split('_');
            INI.WriteINI(Application.StartupPath + "\\Data", "Point", split[split.Length - 1], name, pvalue);
            switch (split[split.Length - 1])
            {
                case "Pick":
                    if (RobotPoint.Pick.Contains(name))
                    {
                        RobotPoint.Pick.Remove(name);
                    }

                    RobotPoint.Pick.Add(name, pvalue);
                    break;
                case "Put":
                    if (RobotPoint.Put.Contains(name))
                    {
                        RobotPoint.Put.Remove(name);
                    }

                    RobotPoint.Put.Add(name, pvalue);
                    break;
                case "Laser":
                    if (RobotPoint.Laser.Contains(name))
                    {
                        RobotPoint.Laser.Remove(name);
                    }

                    RobotPoint.Laser.Add(name, pvalue);
                    break;
            }
        }

        public static void GetStationInfo()
        {
            try
            {
                LianxuWarningCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "NGSetting", "LianXuCount", "3"));
                WarningStopUse = Convert.ToBoolean(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "NGSetting", "StopUse", "true"));
                pcruntimeset = INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "PCTime", "Time", "99,23").Split(',');
                LoginTimeOut = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "Login", "TimeOut", "10"));
                GoldenNG_SwitchMode = INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "Golden", "GoldenNG_SwitchMode", "0") == "1" ? true : false;

                PassDUTCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "Pass", "0"));
                NGDUTCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "NG", "0"));
                WarningDUTCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "All", "Warning", "0"));


                Station.Count = 0;
                Station.Name = new Hashtable();
                Station.Index = new Hashtable();
                Station.TimeOut = new Hashtable();
                Station.NumberList = new Hashtable();

                Station.GoldenTestTime = new Hashtable();
                Station.GoldenTestTimeOnce = new Hashtable();
                Station.GoldenLastTimeRecord = new Hashtable();
                Station.GroupPriority = new Hashtable();
                Station.FixturePriority = new Hashtable();
                Station.Group = new Hashtable();
                Station.Buffer = new Hashtable();
                Station.WaitTestBuffer = new Hashtable();
                Station.ReTestBuffer = new Hashtable();
                Station.TouLiao = new Hashtable();
                Station.TouLiaoIO = new Hashtable();
                Station.TouLiaoCount = new Hashtable();
                Station.PassZone = new Hashtable();
                Station.PassZoneIO = new Hashtable();
                Station.PassZoneCount = new Hashtable();
                Station.NGZone = new Hashtable();
                Station.NGZoneIO = new Hashtable();
                Station.NGZoneCount = new Hashtable();
                Station.TanZhenLastTestTime = new Hashtable();

                RobotPoint.Pick = new Hashtable();
                RobotPoint.Put = new Hashtable();
                RobotPoint.Laser = new Hashtable();

                HaoCai.Name = new Hashtable();
                HaoCai.HType = new Hashtable();
                HaoCai.Spec = new Hashtable();
                HaoCai.UseCount = new Hashtable();
                HaoCai.HistoryUseCount = new Hashtable();

                ArrayList grouparr = new ArrayList();

                Station.NameAll = INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Name", "StationName", "PCBA").Split(',');

                Station.TXPower = INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TXPower", "StationName", "");
                Station.GRR = INI.ReadINI(Application.StartupPath + "\\Data", "Station", "GRR", "StationName", "");
                Station.TanZhenStation = INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TanZhen", "StationName", "");

                GRR.LoopCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "GRR", "Loop_Count", "3"));
                GRR.DUTCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "GRR", "DUT_Count", "10"));
                GRR.TestCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "GRR", "Test_Count", "3"));

                for (int i = 0; i < Station.NameAll.Length; i++)
                {
                    int Count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Count", Station.NameAll[i] + "_Count", "12"));
                    int group = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Group", Station.NameAll[i] + "_Group", "0"));
                    string Bufferkind = INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "Kind", Station.NameAll[i], "0");

                    int WaitCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "WaitTest", Station.NameAll[i], "0"));
                    int ReCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "ReTest", Station.NameAll[i], "0"));

                    Station.TimeOut.Add(Station.NameAll[i], INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Timeout", Station.NameAll[i] + "_Timeout", "500"));
                    Station.Group.Add(Station.NameAll[i], group);
                    Station.Buffer.Add(Station.NameAll[i], Bufferkind);
                    Station.WaitTestBuffer.Add(Station.NameAll[i], WaitCount);
                    Station.ReTestBuffer.Add(Station.NameAll[i], ReCount);

                    for (int t1 = 0; t1 < WaitCount; t1++)
                    {
                        AddPoint(Station.NameAll[i] + "_待測Buffer_" + Convert.ToString(t1 + 1));
                    }
                    for (int t2 = 0; t2 < ReCount; t2++)
                    {
                        AddPoint(Station.NameAll[i] + "_複測Buffer_" + Convert.ToString(t2 + 1));
                    }

                    if (!Station.GroupPriority.Contains(group))
                    {
                        int prioritysetting1 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Priority", "Group", "Group" + group.ToString(), "0"));
                        Station.GroupPriority.Add(group, prioritysetting1);
                    }

                    if (!grouparr.Contains(group))
                    {
                        grouparr.Add(group);
                    }

                    int[] List = new int[Count];
                    for (int j = 0; j < Count; j++)
                    {
                        int number = j + 1 + Station.Count;
                        List[j] = number;
                        Station.Name.Add(number, Station.NameAll[i]);
                        Station.Index.Add(number, i);
                        string goldentime = INI.ReadINI(Application.StartupPath + "\\Data", "GoldenSample", "DayTime", Station.NameAll[i] + "_" + number.ToString(), "");
                        string lasttesttime = INI.ReadINI(Application.StartupPath + "\\Data", "GoldenSample", "LastTime", Station.NameAll[i] + "_" + number.ToString(), "");
                        string lasttesttime2 = INI.ReadINI(Application.StartupPath + "\\Data", "TanZhen", "LastTime", Station.NameAll[i] + "_" + number.ToString(), "");
                        int prioritysetting2 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Priority", "Fixture", Station.NameAll[i] + "_" + number.ToString(), "0"));
                        int nshow = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Show", Station.NameAll[i] + "_" + number.ToString(), "1"));
                        Station.GoldenTestTime.Add(number, goldentime);
                        Station.GoldenLastTimeRecord.Add(number, lasttesttime);
                        Station.FixturePriority.Add(number, prioritysetting2);
                        Station.TanZhenLastTestTime.Add(number, lasttesttime2);

                        AddPoint("治具_" + number.ToString());

                    }

                    Station.NumberList.Add(Station.NameAll[i], List);
                    Station.Count += Count;

                }

                for (int g = 0; g < grouparr.Count; g++)
                {
                    string ngroup = "g" + grouparr[g].ToString();
                    string touliaokind = INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Kind", "0");
                    Station.TouLiao.Add(ngroup, touliaokind);
                    int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", "0"));
                    Station.TouLiaoCount.Add(ngroup, count);
                    for (int t = 0; t < count; t++)
                    {
                        int ioindex = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_" + Convert.ToString(t + 1), "0"));
                        Station.TouLiaoIO.Add(ngroup + "_" + Convert.ToString(t + 1), ioindex);

                        AddPoint("投料點_" + "g" + grouparr[g].ToString() + "_" + Convert.ToString(t + 1));

                    }

                    int count2 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", "0"));
                    Station.PassZoneCount.Add(ngroup, count2);
                    for (int t1 = 0; t1 < count2; t1++)
                    {
                        int ioindex1 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_" + Convert.ToString(t1 + 1), "0"));
                        Station.PassZoneIO.Add(ngroup + "_" + Convert.ToString(t1 + 1), ioindex1);

                        AddPoint("PASS區_" + "g" + grouparr[g].ToString() + "_" + Convert.ToString(t1 + 1));

                    }

                    int count3 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", "0"));
                    Station.NGZoneCount.Add(ngroup, count3);
                    for (int t2 = 0; t2 < count3; t2++)
                    {
                        int ioindex2 = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_" + Convert.ToString(t2 + 1), "0"));
                        Station.NGZoneIO.Add(ngroup + "_" + Convert.ToString(t2 + 1), ioindex2);

                        AddPoint("NG區_" + "g" + grouparr[g].ToString() + "_" + Convert.ToString(t2 + 1));

                    }
                }

                AddPoint("標準件區");


                Station.GoldenIOindex = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "GoldenIO", "IO", "0"));
                Station.TanZhenIOindex = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TanZhenIO", "IO", "0"));


                HaoCai.Count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "Count", "Count", "0"));
                for (int h1 = 0; h1 < HaoCai.Count; h1++)
                {
                    string name = INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "Name", "Name_" + Convert.ToString(h1 + 1), "耗材" + Convert.ToString(h1 + 1));
                    string htype = INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "HType", "HType_" + Convert.ToString(h1 + 1), "");
                    double spec = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "Spec", "Spec_" + Convert.ToString(h1 + 1), "999999"));
                    double usecount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + Convert.ToString(h1 + 1), "0"));
                    double historyusecount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "HaoCai", "HistoryUseCount", "HistoryUseCount_" + Convert.ToString(h1 + 1), "0"));

                    HaoCai.Name.Add(h1 + 1, name);
                    HaoCai.HType.Add(h1 + 1, htype);
                    HaoCai.Spec.Add(h1 + 1, spec);

                    HaoCai.UseCount.Add(h1 + 1, usecount);
                    HaoCai.HistoryUseCount.Add(h1 + 1, historyusecount);
                }

                if (INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Fixture", "Use", "0") == "0")
                {
                    bControlFixture = false;
                }
                else
                {
                    bControlFixture = true;
                }

                if (QUEUE != null)
                {
                    QUEUE.Clear();
                    QUEUE = null;
                }
                QUEUE = new ATSQueue(Station.Count + 1);
                bShowATS = new bool[Station.Count];
                bTestGolden = new bool[Station.Count];
                for (int p = 0; p < Station.Count; p++)
                {
                    if (INI.ReadINI(Application.StartupPath + "\\Data", "Station", "Show", "Fix_" + Convert.ToInt32(p + 1), "1") == "1")
                    {
                        bShowATS[p] = true;
                    }
                    else
                    {
                        bShowATS[p] = false;
                    }
                    bTestGolden[p] = false;
                }
                RobotDoneOver_ByStation = new bool[Station.Count];
                bAlreadyGetStationInfo = true;
            }
            catch (Exception ex)
            {
                MessageBox.Show("加載站別設定錯誤：\r\n" + ex.ToString());
            }

        }

        public static void SetControlFix(bool buse)
        {
            if (buse)
            {
                if (!bControlFixture)
                {
                    bControlFixture = true;
                    INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Fixture", "Use", "1");
                }

            }
            else
            {
                if (bControlFixture)
                {
                    bControlFixture = false;
                    INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Fixture", "Use", "0");
                }
            }
        }

        public static void SetStationName(string newstations)
        {
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Name", "StationName", newstations);
        }

        public static void SetLianXuNG(int count, bool bstopused)
        {
            LianxuWarningCount = count;
            WarningStopUse = bstopused;
            INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "NGSetting", "LianXuCount", count.ToString());
            INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "NGSetting", "StopUse", bstopused.ToString());
        }

        public static void SetPCRuntime(int hour, int minute)
        {
            string time = hour.ToString() + "," + minute.ToString();
            pcruntimeset = time.Split(',');
            INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "PCTime", "Time", time);
        }

        public static void SetLoginTimeOut(int timeout)
        {
            LoginTimeOut = timeout;
            INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "Login", "TimeOut", timeout.ToString());
        }

        public static void SetGoldenNGSwitchMode(bool bswitch)
        {
            GoldenNG_SwitchMode = bswitch;
            if (bswitch)
                INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "Golden", "GoldenNG_SwitchMode", "1");
            else
                INI.WriteINI(Application.StartupPath + "\\Data", "Setting", "Golden", "GoldenNG_SwitchMode", "0");
        }

        public static void SetStationCount(string station, int Count)
        {
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Count", station + "_Count", Count.ToString());
        }

        public static void SetStationTimeout(string station, int timeout)
        {
            if (Station.TimeOut.Contains(station))
            {
                Station.TimeOut.Remove(station);
            }
            Station.TimeOut.Add(station, timeout);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Timeout", station + "_Timeout", timeout.ToString());
        }

        public static void SetGoldenTime(int StationNum, string newsetting)
        {
            if (Station.GoldenTestTime.Contains(StationNum))
            {
                Station.GoldenTestTime.Remove(StationNum);
            }
            if (Station.GoldenTestTimeOnce.Contains(StationNum))
            {
                Station.GoldenTestTimeOnce.Remove(StationNum);
            }
            Station.GoldenTestTime.Add(StationNum, newsetting);

            INI.WriteINI(Application.StartupPath + "\\Data", "GoldenSample", "DayTime", Station.Name[StationNum].ToString() + "_" + StationNum.ToString(), newsetting);

        }

        public static void SetGoldenTimeOnce(int StationNum, string newsetting)
        {
            if (Station.GoldenTestTimeOnce.Contains(StationNum))
            {
                Station.GoldenTestTimeOnce.Remove(StationNum);
            }
            if (Station.GoldenTestTime.Contains(StationNum))
            {
                Station.GoldenTestTime.Remove(StationNum);
            }
            Station.GoldenTestTimeOnce.Add(StationNum, newsetting);
            INI.WriteINI(Application.StartupPath + "\\Data", "GoldenSample", "DayTime", Station.Name[StationNum].ToString() + "_" + StationNum.ToString(), "");
        }

        public static void ClearGoldenSetting(int StationNum)
        {
            if (Station.GoldenTestTime.Contains(StationNum))
            {
                Station.GoldenTestTime.Remove(StationNum);
            }
            if (Station.GoldenTestTimeOnce.Contains(StationNum))
            {
                Station.GoldenTestTimeOnce.Remove(StationNum);
            }

            INI.WriteINI(Application.StartupPath + "\\Data", "GoldenSample", "DayTime", Station.Name[StationNum].ToString() + "_" + StationNum.ToString(), "");
        }

        public static void SetFixShow(int StationNum, bool bshow)
        {
            if (bshow)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Show", "Fix_" + StationNum.ToString(), "1");
            }
            else
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Show", "Fix_" + StationNum.ToString(), "0");
            }
        }

        public static void SetGoldenLastTestTime(int StationNum, DateTime newsetting)
        {
            if (Station.GoldenLastTimeRecord.Contains(StationNum))
            {
                Station.GoldenLastTimeRecord.Remove(StationNum);
            }
            Station.GoldenLastTimeRecord.Add(StationNum, newsetting);

            INI.WriteINI(Application.StartupPath + "\\Data", "GoldenSample", "LastTime", Station.Name[StationNum].ToString() + "_" + StationNum.ToString(), newsetting.ToString("yyyy/MM/dd  HH:mm:ss"));

        }

        public static void SetGoldenIOindex(int indexs)
        {
            Station.GoldenIOindex = indexs;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "GoldenIO", "IO", indexs.ToString());
        }

        public static void SetGRRStation(string stationname)
        {
            Station.GRR = stationname;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "GRR", "StationName", stationname);
        }

        public static void SetGRRDUTCount(int dutcount)
        {
            GRR.DUTCount = dutcount;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "GRR", "DUT_Count", dutcount.ToString());
        }

        public static void SetGRRLoopCount(int loopcount)
        {
            GRR.LoopCount = loopcount;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "GRR", "Loop_Count", loopcount.ToString());
        }

        public static void SetGRRTestCount(int testcount)
        {
            GRR.TestCount = testcount;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "GRR", "Test_Count", testcount.ToString());
        }

        public static void SetTanZhenStation(string stationname)
        {
            Station.TanZhenStation = stationname;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TanZhen", "StationName", stationname);
        }



        public static void SetTanZhenIOindex(int indexs)
        {
            Station.TanZhenIOindex = indexs;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TanZhenIO", "IO", indexs.ToString());
        }

        public static void SetGroupPriority(int Group, int Priority)
        {
            if (Station.GroupPriority.Contains(Group))
            {
                Station.GroupPriority.Remove(Group);
            }

            Station.GroupPriority.Add(Group, Priority);
            INI.WriteINI(Application.StartupPath + "\\Data", "Priority", "Group", "Group" + Group.ToString(), Priority.ToString());
        }

        public static void SetFixtruePriority(int StationNum, int Priority)
        {
            if (Station.FixturePriority.Contains(StationNum))
            {
                Station.FixturePriority.Remove(StationNum);
            }

            Station.FixturePriority.Add(StationNum, Priority);
            INI.WriteINI(Application.StartupPath + "\\Data", "Priority", "Fixture", Station.Name[StationNum].ToString() + "_" + StationNum.ToString(), Priority.ToString());
        }

        public static void SetGroup(string StationName, int group)
        {
            if (Station.Group.Contains(StationName))
            {
                Station.Group.Remove(StationName);
            }

            Station.Group.Add(StationName, group);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "Group", StationName + "_Group", group.ToString());
        }

        public static void SetStationBuffer(string station, string kind)
        {
            if (Station.Buffer.Contains(station))
            {
                Station.Buffer.Remove(station);
            }
            Station.Buffer.Add(station, kind);
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "Kind", station, kind);
        }

        public static void SetWaitTestBuffer(string station, int Count)
        {
            int oldcount = Convert.ToInt32(Station.WaitTestBuffer[station]);
            for (int i = 0; i < oldcount; i++)
            {
                string name = station + "_待測Buffer_" + Convert.ToString(i + 1);
                RobotPoint.Pick.Remove(name + "_Pick");
                RobotPoint.Put.Remove(name + "_Put");
                RobotPoint.Laser.Remove(name + "_Laser");
            }

            if (Station.WaitTestBuffer.Contains(station))
            {
                Station.WaitTestBuffer.Remove(station);
            }
            Station.WaitTestBuffer.Add(station, Count);
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "WaitTest", station, Count.ToString());

            for (int j = 0; j < Count; j++)
            {
                string name = station + "_待測Buffer_" + Convert.ToString(j + 1);
                RobotPoint.Pick.Add(name + "_Pick", ReadPoint(name + "_Pick"));
                RobotPoint.Put.Add(name + "_Put", ReadPoint(name + "_Put"));
                RobotPoint.Laser.Add(name + "_Laser", ReadPoint(name + "_Laser"));
            }
        }

        public static void SetReTestBuffer(string station, int Count)
        {
            int oldcount = Convert.ToInt32(Station.ReTestBuffer[station]);
            for (int i = 0; i < oldcount; i++)
            {
                string name = station + "_複測Buffer_" + Convert.ToString(i + 1);
                RobotPoint.Pick.Remove(name + "_Pick");
                RobotPoint.Put.Remove(name + "_Put");
                RobotPoint.Laser.Remove(name + "_Laser");
            }

            if (Station.ReTestBuffer.Contains(station))
            {
                Station.ReTestBuffer.Remove(station);
            }
            Station.ReTestBuffer.Add(station, Count);
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "ReTest", station, Count.ToString());

            for (int j = 0; j < Count; j++)
            {
                string name = station + "_複測Buffer_" + Convert.ToString(j + 1);
                RobotPoint.Pick.Add(name + "_Pick", ReadPoint(name + "_Pick"));
                RobotPoint.Put.Add(name + "_Put", ReadPoint(name + "_Put"));
                RobotPoint.Laser.Add(name + "_Laser", ReadPoint(name + "_Laser"));
            }
        }

        public static void SetWaitTestInfo(string station, int ID, int FixNum, string SN)
        {
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "WaitFix", station + "_" + ID.ToString(), FixNum.ToString());
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "WaitSN", station + "_" + ID.ToString(), SN);
        }

        public static void GetWaitTestInfo(string station, int ID, ref  int FixNum, ref  string SN)
        {
            FixNum = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "WaitFix", station + "_" + ID.ToString(), "0"));
            SN = INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "WaitSN", station + "_" + ID.ToString(), "NONE");
        }

        public static void SetReTestInfo(string station, int ID, int FixNum, string SN)
        {
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "ReFix", station + "_" + ID.ToString(), FixNum.ToString());
            INI.WriteINI(Application.StartupPath + "\\Data", "Buffer", "ReSN", station + "_" + ID.ToString(), SN);
        }

        public static void GetReTestInfo(string station, int ID, ref  int FixNum, ref  string SN)
        {
            FixNum = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "ReFix", station + "_" + ID.ToString(), "0"));
            SN = INI.ReadINI(Application.StartupPath + "\\Data", "Buffer", "ReSN", station + "_" + ID.ToString(), "NONE");
        }

        public static void SetTouLiaoKind(int group, string kind)
        {
            string ngroup = "g" + group.ToString();

            if (Station.TouLiao.Contains(ngroup))
            {
                Station.TouLiao.Remove(ngroup);
            }
            Station.TouLiao.Add(ngroup, kind);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Kind", kind);
        }

        public static void AddTouLiao(int group, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", "0"));
            count++;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", count.ToString());
            Station.TouLiaoIO.Add(ngroup + "_" + count.ToString(), ioindex);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_" + count.ToString(), ioindex.ToString());
            if (Station.TouLiaoCount.Contains(ngroup))
            {
                Station.TouLiaoCount.Remove(ngroup);
            }
            Station.TouLiaoCount.Add(ngroup, count);

            string name = "投料點_" + ngroup + "_" + count.ToString();
            RobotPoint.Pick.Add(name + "_Pick", ReadPoint(name + "_Pick"));
            RobotPoint.Put.Add(name + "_Put", ReadPoint(name + "_Put"));
            RobotPoint.Laser.Add(name + "_Laser", ReadPoint(name + "_Laser"));
        }

        public static void SetTouLiao(int group, int touliaoindex, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", "0"));
            if (touliaoindex <= count)
            {
                if (Station.TouLiaoIO.Contains(ngroup + "_" + touliaoindex))
                    Station.TouLiaoIO.Remove(ngroup + "_" + touliaoindex.ToString());

                Station.TouLiaoIO.Add(ngroup + "_" + touliaoindex.ToString(), ioindex);
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_" + touliaoindex.ToString(), ioindex.ToString());


            }
        }



        public static void DeleteTouLiao(int group)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", "0"));
            if (count > 0)
            {
                string name = "投料點_" + ngroup + "_" + count.ToString();
                RobotPoint.Pick.Remove(name + "_Pick");
                RobotPoint.Put.Remove(name + "_Put");
                RobotPoint.Laser.Remove(name + "_Laser");

                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_" + count.ToString(), "");
                Station.TouLiaoIO.Remove(ngroup + "_" + count.ToString());
                count--;
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "TouLiao", ngroup + "_Count", count.ToString());
                if (Station.TouLiaoCount.Contains(ngroup))
                {
                    Station.TouLiaoCount.Remove(ngroup);
                }
                Station.TouLiaoCount.Add(ngroup, count);


            }
        }


        public static void AddPassZone(int group, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", "0"));
            count++;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", count.ToString());
            Station.PassZoneIO.Add(ngroup + "_" + count.ToString(), ioindex);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_" + count.ToString(), ioindex.ToString());
            if (Station.PassZoneCount.Contains(ngroup))
            {
                Station.PassZoneCount.Remove(ngroup);
            }
            Station.PassZoneCount.Add(ngroup, count);

            string name = "PASS區_" + ngroup + "_" + count.ToString();
            RobotPoint.Pick.Add(name + "_Pick", ReadPoint(name + "_Pick"));
            RobotPoint.Put.Add(name + "_Put", ReadPoint(name + "_Put"));
            RobotPoint.Laser.Add(name + "_Laser", ReadPoint(name + "_Laser"));
        }

        public static void SetPassZone(int group, int passindex, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", "0"));
            if (passindex <= count)
            {
                if (Station.PassZoneIO.Contains(ngroup + "_" + passindex))
                    Station.PassZoneIO.Remove(ngroup + "_" + passindex.ToString());

                Station.PassZoneIO.Add(ngroup + "_" + passindex.ToString(), ioindex);
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_" + passindex.ToString(), ioindex.ToString());


            }
        }

        public static void DeletePassZone(int group)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", "0"));
            if (count > 0)
            {
                string name = "PASS區_" + ngroup + "_" + count.ToString();
                RobotPoint.Pick.Remove(name + "_Pick");
                RobotPoint.Put.Remove(name + "_Put");
                RobotPoint.Laser.Remove(name + "_Laser");

                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_" + count.ToString(), "");
                Station.PassZoneIO.Remove(ngroup + "_" + count.ToString());
                count--;
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "PassZone", ngroup + "_Count", count.ToString());
                if (Station.PassZoneCount.Contains(ngroup))
                {
                    Station.PassZoneCount.Remove(ngroup);
                }
                Station.PassZoneCount.Add(ngroup, count);


            }
        }


        public static void AddNGZone(int group, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", "0"));
            count++;
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", count.ToString());
            Station.NGZoneIO.Add(ngroup + "_" + count.ToString(), ioindex);
            INI.WriteINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_" + count.ToString(), ioindex.ToString());
            if (Station.NGZoneCount.Contains(ngroup))
            {
                Station.NGZoneCount.Remove(ngroup);
            }
            Station.NGZoneCount.Add(ngroup, count);

            string name = "NG區_" + ngroup + "_" + count.ToString();
            RobotPoint.Pick.Add(name + "_Pick", ReadPoint(name + "_Pick"));
            RobotPoint.Put.Add(name + "_Put", ReadPoint(name + "_Put"));
            RobotPoint.Laser.Add(name + "_Laser", ReadPoint(name + "_Laser"));
        }

        public static void SetNGZone(int group, int passindex, int ioindex)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", "0"));
            if (passindex <= count)
            {
                if (Station.NGZoneIO.Contains(ngroup + "_" + passindex))
                    Station.NGZoneIO.Remove(ngroup + "_" + passindex.ToString());

                Station.NGZoneIO.Add(ngroup + "_" + passindex.ToString(), ioindex);
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_" + passindex.ToString(), ioindex.ToString());


            }
        }

        public static void DeleteNGZone(int group)
        {
            string ngroup = "g" + group.ToString();
            int count = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", "0"));
            if (count > 0)
            {
                string name = "NG區_" + ngroup + "_" + count.ToString();
                RobotPoint.Pick.Remove(name + "_Pick");
                RobotPoint.Put.Remove(name + "_Put");
                RobotPoint.Laser.Remove(name + "_Laser");

                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_" + count.ToString(), "");
                Station.NGZoneIO.Remove(ngroup + "_" + count.ToString());
                count--;
                INI.WriteINI(Application.StartupPath + "\\Data", "Station", "NGZone", ngroup + "_Count", count.ToString());
                if (Station.NGZoneCount.Contains(ngroup))
                {
                    Station.NGZoneCount.Remove(ngroup);
                }
                Station.NGZoneCount.Add(ngroup, count);


            }
        }


        public static void AddHaoCai()
        {

            HaoCai.Count++;
            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Count", "Count", HaoCai.Count.ToString());

            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Name", "Name_" + HaoCai.Count.ToString(), "耗材" + HaoCai.Count.ToString());
            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HType", "HType_" + HaoCai.Count.ToString(), "");
            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Spec", "Spec_" + HaoCai.Count.ToString(), "999999");
            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + HaoCai.Count.ToString(), "0");
            INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HistoryUseCount", "HistoryUseCount_" + HaoCai.Count.ToString(), "0");

            HaoCai.Name.Add(HaoCai.Count, "耗材" + HaoCai.Count.ToString());
            HaoCai.HType.Add(HaoCai.Count, "");
            HaoCai.Spec.Add(HaoCai.Count, 999999);

            HaoCai.UseCount.Add(HaoCai.Count, 0);
            HaoCai.HistoryUseCount.Add(HaoCai.Count, 0);
        }

        public static void DeleteHaoCai()
        {
            if (HaoCai.Count > 0)
            {

                //INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Name", "Name_" + HaoCai.Count.ToString(), "耗材" + HaoCai.Count.ToString());
                //INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HType", "HType_" + HaoCai.Count.ToString(), "");
                //INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Spec", "Spec_" + HaoCai.Count.ToString(), "999999");
                //INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + HaoCai.Count.ToString(), "0");
                //INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HistoryUseCount", "HistoryUseCount_" + HaoCai.Count.ToString(), "0");

                HaoCai.Name.Remove(HaoCai.Count);
                HaoCai.HType.Remove(HaoCai.Count);
                HaoCai.Spec.Remove(HaoCai.Count);

                HaoCai.UseCount.Remove(HaoCai.Count);
                HaoCai.HistoryUseCount.Remove(HaoCai.Count);

                HaoCai.Count--;
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Count", "Count", HaoCai.Count.ToString());

            }
        }

        public static void ModifyHaoCai_NameType(int indexnum, string name, string htype)
        {
            if (indexnum <= Produce.HaoCai.Count)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Name", "Name_" + indexnum.ToString(), name);
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HType", "HType_" + indexnum.ToString(), htype);

                HaoCai.Name[indexnum] = name;
                HaoCai.HType[indexnum] = htype;
            }
        }

        public static void ModifyHaoCai_Spec(int indexnum, double spec)
        {
            if (indexnum <= Produce.HaoCai.Count)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "Spec", "Spec_" + indexnum.ToString(), spec.ToString());
                HaoCai.Spec[indexnum] = spec;
            }

        }

        public static void ClearHaoCai_UseCount(int indexnum)
        {
            if (indexnum <= Produce.HaoCai.Count)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + indexnum.ToString(), "0");
                HaoCai.UseCount[indexnum] = 0;
            }

        }

        public static void ClearHaoCai_HistoryUseCount(int indexnum)
        {
            if (indexnum <= Produce.HaoCai.Count)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + indexnum.ToString(), "0");
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HistoryUseCount", "HistoryUseCount_" + indexnum.ToString(), "0");
                HaoCai.UseCount[indexnum] = 0;
                HaoCai.HistoryUseCount[indexnum] = 0;
            }

        }

        public static void AddHaoCai_UseCount(int indexnum)
        {
            if (indexnum <= Produce.HaoCai.Count)
            {
                double oldcount = Convert.ToDouble(HaoCai.UseCount[indexnum]);
                double oldcount2 = Convert.ToDouble(HaoCai.HistoryUseCount[indexnum]);

                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "UseCount", "UseCount_" + indexnum.ToString(), Convert.ToString(oldcount + 1));
                INI.WriteINI(Application.StartupPath + "\\Data", "HaoCai", "HistoryUseCount", "HistoryUseCount_" + indexnum.ToString(), Convert.ToString(oldcount2 + 1));
                HaoCai.UseCount[indexnum] = oldcount + 1;
                HaoCai.HistoryUseCount[indexnum] = oldcount2 + 1;
            }

        }

    }
}
