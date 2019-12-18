namespace AutoMationTest.UI
{
    partial class NormalBuffer
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
            this.tbox_SN = new System.Windows.Forms.TextBox();
            this.button1 = new System.Windows.Forms.Button();
            this.tBox_Fix = new System.Windows.Forms.TextBox();
            this.bt_id = new System.Windows.Forms.Button();
            this.jianBianPanel1 = new AutoMationTest.UI.JianBianPanel();
            this.SuspendLayout();
            // 
            // tbox_SN
            // 
            this.tbox_SN.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.tbox_SN.Enabled = false;
            this.tbox_SN.Font = new System.Drawing.Font("Microsoft YaHei UI Light", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.tbox_SN.Location = new System.Drawing.Point(16, 70);
            this.tbox_SN.Name = "tbox_SN";
            this.tbox_SN.Size = new System.Drawing.Size(149, 15);
            this.tbox_SN.TabIndex = 3;
            this.tbox_SN.Text = "NONE";
            this.tbox_SN.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // button1
            // 
            this.button1.Font = new System.Drawing.Font("新細明體", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(136)));
            this.button1.Location = new System.Drawing.Point(120, 8);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(45, 23);
            this.button1.TabIndex = 11;
            this.button1.Text = "更改";
            this.button1.UseVisualStyleBackColor = true;
            this.button1.Click += new System.EventHandler(this.button1_Click);
            // 
            // tBox_Fix
            // 
            this.tBox_Fix.Enabled = false;
            this.tBox_Fix.Font = new System.Drawing.Font("Calibri", 9.75F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.tBox_Fix.Location = new System.Drawing.Point(51, 8);
            this.tBox_Fix.Name = "tBox_Fix";
            this.tBox_Fix.Size = new System.Drawing.Size(63, 23);
            this.tBox_Fix.TabIndex = 5;
            this.tBox_Fix.Text = "0";
            this.tBox_Fix.TextAlign = System.Windows.Forms.HorizontalAlignment.Center;
            // 
            // bt_id
            // 
            this.bt_id.BackColor = System.Drawing.Color.WhiteSmoke;
            this.bt_id.Enabled = false;
            this.bt_id.FlatAppearance.BorderColor = System.Drawing.Color.LightGray;
            this.bt_id.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.bt_id.Font = new System.Drawing.Font("Calibri Light", 8.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.bt_id.ForeColor = System.Drawing.Color.DarkOliveGreen;
            this.bt_id.Location = new System.Drawing.Point(16, 8);
            this.bt_id.Name = "bt_id";
            this.bt_id.Size = new System.Drawing.Size(29, 23);
            this.bt_id.TabIndex = 12;
            this.bt_id.Text = "0";
            this.bt_id.UseVisualStyleBackColor = false;
            // 
            // jianBianPanel1
            // 
            this.jianBianPanel1.CenterColor = System.Drawing.Color.White;
            this.jianBianPanel1.Location = new System.Drawing.Point(16, 36);
            this.jianBianPanel1.Name = "jianBianPanel1";
            this.jianBianPanel1.Size = new System.Drawing.Size(149, 27);
            this.jianBianPanel1.SurroundColor = System.Drawing.Color.WhiteSmoke;
            this.jianBianPanel1.TabIndex = 0;
            // 
            // NormalBuffer
            // 
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.None;
            this.BackColor = System.Drawing.Color.Linen;
            this.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.Controls.Add(this.bt_id);
            this.Controls.Add(this.tBox_Fix);
            this.Controls.Add(this.button1);
            this.Controls.Add(this.tbox_SN);
            this.Controls.Add(this.jianBianPanel1);
            this.DoubleBuffered = true;
            this.Name = "NormalBuffer";
            this.Size = new System.Drawing.Size(181, 96);
            this.Load += new System.EventHandler(this.NormalBuffer_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private JianBianPanel jianBianPanel1;
        private System.Windows.Forms.TextBox tbox_SN;
        private System.Windows.Forms.TextBox tBox_Fix;
        private System.Windows.Forms.Button button1;
        private System.Windows.Forms.Button bt_id;
    }
}
