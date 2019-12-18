namespace AutoMationTest.UI
{
    partial class NormalTouLiao
    {
        /// <summary> 
        /// 設計工具所需的變數。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清除任何使用中的資源。
        /// </summary>
        /// <param name="disposing">如果應該處置 Managed 資源則為 true，否則為 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 元件設計工具產生的程式碼

        /// <summary> 
        /// 此為設計工具支援所需的方法 - 請勿使用程式碼編輯器
        /// 修改這個方法的內容。
        /// </summary>
        private void InitializeComponent()
        {
            this.bt_id = new System.Windows.Forms.Button();
            this.button1 = new System.Windows.Forms.Button();
            this.IOLIST = new System.Windows.Forms.ComboBox();
            this.label1 = new System.Windows.Forms.Label();
            this.jianBianPanel1 = new AutoMationTest.UI.JianBianPanel();
            this.SuspendLayout();
            // 
            // bt_id
            // 
            this.bt_id.BackColor = System.Drawing.Color.WhiteSmoke;
            this.bt_id.Enabled = false;
            this.bt_id.FlatAppearance.BorderColor = System.Drawing.Color.LightGray;
            this.bt_id.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.bt_id.Font = new System.Drawing.Font("Calibri Light", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.bt_id.ForeColor = System.Drawing.Color.DarkOliveGreen;
            this.bt_id.Location = new System.Drawing.Point(17, 12);
            this.bt_id.Name = "bt_id";
            this.bt_id.Size = new System.Drawing.Size(29, 23);
            this.bt_id.TabIndex = 17;
            this.bt_id.Text = "0";
            this.bt_id.UseVisualStyleBackColor = false;
            // 
            // button1
            // 
            this.button1.Font = new System.Drawing.Font("新細明體", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(136)));
            this.button1.Location = new System.Drawing.Point(187, 12);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(45, 23);
            this.button1.TabIndex = 16;
            this.button1.Text = "更改";
            this.button1.UseVisualStyleBackColor = true;
            this.button1.Click += new System.EventHandler(this.button1_Click);
            // 
            // IOLIST
            // 
            this.IOLIST.Font = new System.Drawing.Font("微软雅黑", 9.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.IOLIST.FormattingEnabled = true;
            this.IOLIST.Location = new System.Drawing.Point(76, 9);
            this.IOLIST.Name = "IOLIST";
            this.IOLIST.Size = new System.Drawing.Size(103, 27);
            this.IOLIST.TabIndex = 18;
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("微软雅黑", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.label1.Location = new System.Drawing.Point(52, 14);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(22, 17);
            this.label1.TabIndex = 19;
            this.label1.Text = "IO";
            // 
            // jianBianPanel1
            // 
            this.jianBianPanel1.CenterColor = System.Drawing.Color.White;
            this.jianBianPanel1.Location = new System.Drawing.Point(17, 42);
            this.jianBianPanel1.Name = "jianBianPanel1";
            this.jianBianPanel1.Size = new System.Drawing.Size(215, 42);
            this.jianBianPanel1.SurroundColor = System.Drawing.Color.WhiteSmoke;
            this.jianBianPanel1.TabIndex = 13;
            // 
            // NormalTouLiao
            // 
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
            this.BackColor = System.Drawing.SystemColors.GradientInactiveCaption;
            this.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.Controls.Add(this.label1);
            this.Controls.Add(this.IOLIST);
            this.Controls.Add(this.bt_id);
            this.Controls.Add(this.button1);
            this.Controls.Add(this.jianBianPanel1);
            this.Name = "NormalTouLiao";
            this.Size = new System.Drawing.Size(249, 96);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button bt_id;
        private System.Windows.Forms.Button button1;
        private JianBianPanel jianBianPanel1;
        private System.Windows.Forms.Label label1;
        public System.Windows.Forms.ComboBox IOLIST;
    }
}
