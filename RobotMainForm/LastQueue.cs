using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Function;
using System.IO;

namespace RobotMainForm
{
    public partial class LastQueue : Form
    {
        public LastQueue()
        {
            InitializeComponent();
        }

        private void LastQueue_Load(object sender, EventArgs e)
        {
            string sFile = Application.StartupPath + "\\LAST.csv";
            if (File.Exists(sFile))
            {
                DataTable dt = CSVhelper.csv2dt(sFile, 0);
                dataGridView1.DataSource = dt;
            }
        }
    }
}
