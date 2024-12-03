from code.app import app, db, Problem

def add_sample_problems():
    with app.app_context():
        # 清空现有题目
        Problem.query.delete()
        
        # 添加示例题目
        problems = [
            # 简单题目
            Problem(
                title='两数之和',
                content='给定一个整数数组 nums 和一个目标值 target，请你在该数组中找出和为目标值的那两个整数，并返回他们的数组下标。\n示例：nums = [2, 7, 11, 15], target = 9\n返回 [0, 1]',
                answer='[0,1]',
                difficulty=1
            ),
            Problem(
                title='回文数',
                content='判断一个整数是否是回文数。回文数是指正序（从左向右）和倒序（从右向左）读都是一样的整数。\n示例：121 是回文数，-121 不是',
                answer='true',
                difficulty=1
            ),
            Problem(
                title='罗马数字转整数',
                content='给定一个罗马数字，将其转换成整数。\n示例：输入: "III" 输出: 3\n输入: "IV" 输出: 4\n输入: "IX" 输出: 9',
                answer='3',
                difficulty=1
            ),
            
            # 中等题目
            Problem(
                title='最长回文子串',
                content='给定一个字符串 s，找到 s 中最长的回文子串。\n示例：输入 "babad"，输出 "bab" 或 "aba"',
                answer='bab',
                difficulty=2
            ),
            Problem(
                title='盛最多水的容器',
                content='给你 n 个非负整数 a1，a2，...，an，每个数代表坐标中的一个点 (i, ai) 。在坐标内画 n 条垂直线，垂直线 i 的两个端点分别为 (i, ai) 和 (i, 0)。找出其中的两条线，使得它们与 x 轴共同构成的容器可以容纳最多的水。\n示例：输入 [1,8,6,2,5,4,8,3,7] 输出：49',
                answer='49',
                difficulty=2
            ),
            Problem(
                title='三数之和',
                content='给你一个包含 n 个整数的数组 nums，判断 nums 中是否存在三个元素 a，b，c ，使得 a + b + c = 0。请找出所有满足条件且不重复的三元组。\n示例：nums = [-1, 0, 1, 2, -1, -4]，输出：[[-1,-1,2],[-1,0,1]]',
                answer='[[-1,-1,2],[-1,0,1]]',
                difficulty=2
            ),
            
            # 困难题目
            Problem(
                title='正则表达式匹配',
                content='给你一个字符串 s 和一个字符规律 p，请你来实现一个支持 \'.\' 和 \'*\' 的正则表达式匹配。\n\'.\'匹配任意单个字符\n\'*\'匹配零个或多个前面的那一个元素\n示例：输入 s = "aa", p = "a*" 输出：true',
                answer='true',
                difficulty=3
            ),
            Problem(
                title='合并K个排序链表',
                content='合并 k 个排序链表，返回合并后的排序链表。请分析和描述算法的复杂度。\n示例：输入: [1->4->5, 1->3->4, 2->6]，输出: 1->1->2->3->4->4->5->6',
                answer='1->1->2->3->4->4->5->6',
                difficulty=3
            ),
            Problem(
                title='寻找两个正序数组的中位数',
                content='给定两个大小为 m 和 n 的正序（从小到大）数组 nums1 和 nums2。请你找出这两个正序数组的中位数，并且要求算法的时间复杂度为 O(log(m + n))。\n示例：nums1 = [1, 3], nums2 = [2]，输出：2.0',
                answer='2.0',
                difficulty=3
            )
        ]
        
        # 添加所有题目
        for problem in problems:
            db.session.add(problem)
        db.session.commit()

if __name__ == '__main__':
    add_sample_problems()
    print("Sample problems added successfully.")