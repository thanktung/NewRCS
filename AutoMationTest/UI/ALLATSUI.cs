using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;

namespace AutoMationTest.UI
{
    public partial class ALLATSUI : UserControl
    {
        //int CountPerColumn = 4;
        //int RowInterval = 0;
        //int ColumnInterval = 0;
        private const string CategoryName = "ATS模塊集合";
        //string[,] ATS_IP_PORT;
        public TestUI[] ATS;
        int BigCount = 0;

        //Thread connectthread;

        public TabControl tb1 = new TabControl();
        TabPage[] pages;

        private int _columcount = 4;
        /// <summary>
        /// 每一列ATS模塊的數量
        /// </summary>
        [Category(CategoryName)]
        [Description("每一列ATS模塊排列的個數")]
        [DefaultValue((int)4)]
        public int ATSCountPerColumn
        {
            get
            {
                return _columcount;
            }
            set
            {
                _columcount = value;

                //for (int i = 0; i < ATS.Length; i++)
                //{
                //    int shiftX = i / ATSCountPerColumn;
                //    int shiftY = i % ATSCountPerColumn;

                //    int X = 1 + (ATS[i].Size.Width + RowInterval) * shiftX;// +panel1.AutoScrollPosition.X;//+ i * 20 
                //    int Y = 1 + (ATS[i].Size.Height + ColumnInterval) * shiftY;

                //    ATS[i].Location = new Point(X, Y);
                //}
                if (BigCount != 0)
                {
                    for (int p = 0; p < BigCount; p++)
                    {
                        string name = Produce.Station.NameAll[p].ToString();
                        int[] List = (int[])Produce.Station.NumberList[name];

                        for (int i = 0; i < List.Length; i++)
                        {
                            int shiftX = i / ATSCountPerColumn;
                            int shiftY = i % ATSCountPerColumn;

                            int X = 1 + (ATS[List[i] - 1].Size.Width + RowInterval) * shiftX;
                            int Y = 5 + (ATS[List[i] - 1].Size.Height + ColumnInterval) * shiftY;

                            ATS[List[i] - 1].Location = new Point(X, Y);
                        }

                    }
                }
            }
        }

        private int _rowinterval = 25;
        /// <summary>
        /// ATS模塊排列的行間距
        /// </summary>
        [Category(CategoryName)]
        [Description("ATS模塊排列的行間距")]
        [DefaultValue((int)25)]
        public int RowInterval
        {
            get
            {
                return _rowinterval;
            }
            set
            {
                _rowinterval = value;

                //for (int i = 0; i < ATS.Length; i++)
                //{
                //    int shiftX = i / ATSCountPerColumn;
                //    int shiftY = i % ATSCountPerColumn;

                //    int X = 1 + (ATS[i].Size.Width + RowInterval) * shiftX;// +panel1.AutoScrollPosition.X;//+ i * 20 
                //    int Y = 1 + (ATS[i].Size.Height + ColumnInterval) * shiftY;

                //    ATS[i].Location = new Point(X, Y);
                //}

                if (BigCount != 0)
                {
                    for (int p = 0; p < BigCount; p++)
                    {
                        string name = Produce.Station.NameAll[p].ToString();
                        int[] List = (int[])Produce.Station.NumberList[name];

                        for (int i = 0; i < List.Length; i++)
                        {
                            int shiftX = i / ATSCountPerColumn;
                            int shiftY = i % ATSCountPerColumn;

                            int X = 1 + (ATS[List[i] - 1].Size.Width + RowInterval) * shiftX;
                            int Y = 5 + (ATS[List[i] - 1].Size.Height + ColumnInterval) * shiftY;

                            ATS[List[i] - 1].Location = new Point(X, Y);
                        }

                    }
                }
            }
        }

        private int _ColumnInterval = 25;
        /// <summary>
        /// ATS模塊排列的列間距
        /// </summary>
        [Category(CategoryName)]
        [Description("ATS模塊排列的列間距")]
        [DefaultValue((int)25)]
        public int ColumnInterval
        {
            get
            {
                return _ColumnInterval;
            }
            set
            {

                _ColumnInterval = value;

                //for (int i = 0; i < ATS.Length; i++)
                //{
                //    int shiftX = i / ATSCountPerColumn;
                //    int shiftY = i % ATSCountPerColumn;

                //    int X = 1 + (ATS[i].Size.Width + RowInterval) * shiftX;// +panel1.AutoScrollPosition.X;//+ i * 20 
                //    int Y = 1 + (ATS[i].Size.Height + ColumnInterval) * shiftY;

                //    ATS[i].Location = new Point(X, Y);
                //}
                if (BigCount != 0)
                {
                    for (int p = 0; p < BigCount; p++)
                    {
                        string name = Produce.Station.NameAll[p].ToString();
                        int[] List = (int[])Produce.Station.NumberList[name];

                        for (int i = 0; i < List.Length; i++)
                        {
                            int shiftX = i / ATSCountPerColumn;
                            int shiftY = i % ATSCountPerColumn;

                            int X = 1 + (ATS[List[i] - 1].Size.Width + RowInterval) * shiftX;
                            int Y = 5 + (ATS[List[i] - 1].Size.Height + ColumnInterval) * shiftY;

                            ATS[List[i] - 1].Location = new Point(X, Y);
                        }

                    }
                }
            }
        }



        private Color pagebackcolor = SystemColors.ActiveCaption;
        /// <summary>
        /// ATS模塊排列的列間距
        /// </summary>
        [Category(CategoryName)]
        [Description("Tabpage的背景顏色")]
        //[DefaultValue(SystemColors.ActiveCaption)]
        public Color PageBackColor
        {
            get
            {
                return pagebackcolor;
            }
            set
            {
                pagebackcolor = value;
                if (BigCount != 0)
                {
                    for (int p = 0; p < BigCount; p++)
                    {
                        pages[p].BackColor = pagebackcolor;
                    }
                }
            }
        }

        private TabAlignment ali = TabAlignment.Top;
        /// <summary>
        /// ATS模塊排列的列間距
        /// </summary>
        [Category(CategoryName)]
        [Description("TabControl的分頁排列方式")]
        //[DefaultValue(SystemColors.ActiveCaption)]
        public TabAlignment TabAliment
        {
            get
            {
                return ali;
            }
            set
            {
                ali = value;
                tb1.Alignment = ali;
            }
        }




        public ALLATSUI()//int nCountPerColumn, int nRowInterval, int nColumnInterval)
        {
            InitializeComponent();

            Produce.GetStationInfo();

            //ATS_IP_PORT = new string[Produce.Station.Count, 2];
            ATS = new TestUI[Produce.Station.Count];

            int X = 0;
            int Y = 0;

            BigCount = Produce.Station.NameAll.Length;

            tb1.Dock = DockStyle.Fill;

            pages = new TabPage[BigCount];


            for (int p = 0; p < BigCount; p++)
            {
                pages[p] = new TabPage();
                pages[p].AutoScroll = true;
                pages[p].Text = Produce.Station.NameAll[p].ToString();
                pages[p].BackColor = PageBackColor;


                string name = Produce.Station.NameAll[p].ToString();
                int[] List = (int[])Produce.Station.NumberList[name];

                for (int i = 0; i < List.Length; i++)
                {
                    int shiftX = i / ATSCountPerColumn;
                    int shiftY = i % ATSCountPerColumn;

                    ATS[List[i] - 1] = new TestUI();
                    ATS[List[i] - 1].StationNumber = List[i];
                    //ATS[List[i] - 1].PassCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data","Test", "Fix_" + List[i].ToString(), "Pass", "0"));
                    //ATS[List[i] - 1].NGCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data","Test", "Fix_" + List[i].ToString(), "NG", "0"));
                    //ATS[List[i] - 1].WarningCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data","Test", "Fix_" + List[i].ToString(), "Warning", "0"));

                    X = 1 + (ATS[List[i] - 1].Size.Width + RowInterval) * shiftX;
                    Y = 5 + (ATS[List[i] - 1].Size.Height + ColumnInterval) * shiftY;

                    ATS[List[i] - 1].Location = new Point(X, Y);
                    pages[p].Controls.Add(ATS[List[i] - 1]);
                }

                tb1.Controls.Add(pages[p]);
            }

            this.Controls.Add(tb1);



            //for (int i = 0; i < ATS.Length; i++)
            //{


            //    int shiftX = i / ATSCountPerColumn;
            //    int shiftY = i % ATSCountPerColumn;

            //    ATS[i] = new TestUI();
            //    ATS[i].StationNumber = i + 1;


            //    X = 1 + (ATS[i].Size.Width + RowInterval) * shiftX;
            //    Y = 1 + (ATS[i].Size.Height + ColumnInterval) * shiftY;

            //    ATS[i].Location = new Point(X, Y);
            //    this.Controls.Add(ATS[i]);
            //}



        }

        //private AutoPanel panel1;



        private void ALLATSUI_Load(object sender, EventArgs e)
        {



            //int X0 = (ATS[0].Size.Width + RowInterval) * 3 - RowInterval + 25;
            //int Y0 = (ATS[0].Size.Height + ColumnInterval) * ATSCountPerColumn - ColumnInterval + 25;
            //this.Size = new Size(X0, Y0);

            //connectthread = new Thread(new ThreadStart(ATSConnect));
            //connectthread.Start();

        }




    }
}
