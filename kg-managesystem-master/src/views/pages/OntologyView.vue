<template>
  <div class="ontology-container">
    <!-- 本体列表 -->
    <div class="header">
      <h2>本体管理</h2>
      <el-button type="primary" @click="showCreateDialog">新建本体</el-button>
    </div>

    <!-- 本体表格 -->
    <el-table :data="ontologyList" style="width: 100%">
      <el-table-column prop="name" label="本体文档名" width="180">
        <template #default="scope">
          <el-input
            v-if="scope.row.isEditing"
            v-model="scope.row.editName"
            @blur="saveEdit(scope.row)"
          />
          <span v-else>{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="文档描述">
        <template #default="scope">
          <el-input
            v-if="scope.row.isEditing"
            v-model="scope.row.editDescription"
            type="textarea"
            autosize
            @blur="saveEdit(scope.row)"
          />
          <span v-else>{{ scope.row.description }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="updateTime" label="修改时间" width="180" />
      <el-table-column label="包含实体" width="200">
        <template #default="scope">
          <el-tag
            v-for="entity in scope.row.entities"
            :key="entity"
            style="margin-right: 5px; margin-bottom: 5px"
          >
            {{ entity }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="scope">
          <el-button
            size="small"
            @click="toggleEdit(scope.row)"
          >
            {{ scope.row.isEditing ? '取消' : '编辑' }}
          </el-button>
          <el-button
            size="small"
            type="danger"
            @click="handleDelete(scope.row)"
          >
            删除
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="handleEdit(scope.row)"
          >
            编辑本体
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建本体对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建本体" width="30%">
      <el-form :model="newOntology" label-width="80px">
        <el-form-item label="文档名">
          <el-input v-model="newOntology.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newOntology.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createOntology">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 本体编辑页面 -->
    <el-dialog v-model="editDialogVisible" :title="`编辑本体 - ${editingOntology.name}`" fullscreen>
      <div class="edit-container">
        <div class="mode-switch">
          <el-button-group>
            <el-button :type="mode === 'table' ? 'primary' : ''" @click="mode = 'table'">表格模式</el-button>
            <el-button :type="mode === 'canvas' ? 'primary' : ''" @click="mode = 'canvas'">画板模式</el-button>
          </el-button-group>
        </div>

        <!-- 表格模式 -->
        <div v-if="mode === 'table'" class="table-mode">
          <!-- 实体区 -->
          <div class="entity-section">
            <h3>实体管理</h3>
            <div class="entity-actions">
              <el-button type="primary" @click="showCreateEntityDialog">新建实体</el-button>
            </div>
            <el-table :data="entities" style="width: 100%">
              <el-table-column prop="name" label="实体名称" width="180" />
              <el-table-column prop="label" label="类标签" width="180" />
              <el-table-column prop="definition" label="定义" />
              <el-table-column label="属性">
                <template #default="scope">
                  <el-tag
                    v-for="(property, index) in scope.row.properties"
                    :key="index"
                    style="margin-right: 5px; margin-bottom: 5px"
                  >
                    {{ property }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="实例">
                <template #default="scope">
                  <el-tag
                    v-for="(instance, index) in scope.row.instances"
                    :key="index"
                    style="margin-right: 5px; margin-bottom: 5px"
                  >
                    {{ instance }}
                  </el-tag>
                </template>
              </el-table-column>

              <el-table-column label="操作" width="180">
                <template #default="scope">
                  <el-button size="small" @click="editEntity(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="deleteEntity(scope.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 关系区 -->
          <div class="relation-section">
            <h3>关系管理</h3>
            <div class="relation-actions">
              <el-button type="primary" @click="showCreateRelationDialog">新建关系</el-button>
            </div>
            <el-table :data="relations" style="width: 100%">
              <el-table-column prop="name" label="关系名称" width="180" />
              <el-table-column prop="label" label="关系标签" width="180" />
              <el-table-column prop="from" label="前键" width="180" />
              <el-table-column prop="to" label="后键" width="180" />
              <el-table-column prop="definition" label="定义" />
              <el-table-column label="操作" width="180">
                <template #default="scope">
                  <el-button size="small" @click="editRelation(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="deleteRelation(scope.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 画板模式 -->
        <div v-if="mode === 'canvas'" class="canvas-mode">
          <div id="ontology-canvas" ref="canvas"></div>
        </div>
      </div>
    </el-dialog>

    <!-- 实体编辑对话框 -->
    <el-dialog v-model="entityDialogVisible" :title="`${isEditingEntity ? '编辑' : '新建'}实体`">
      <el-form :model="currentEntity" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="currentEntity.name" placeholder="实体类名称，必填项"/>
        </el-form-item>
        <el-form-item label="类标签">
          <el-input v-model="currentEntity.label" placeholder="实体类英文标签，选填项"/>
        </el-form-item>
        <el-form-item label="定义">
          <el-input v-model="currentEntity.definition" type="textarea" placeholder="实体类说明，选填项"/>
        </el-form-item>
        <el-form-item label="属性">
          <div v-for="(property, index) in currentEntity.properties" :key="index" class="property-item">
            <el-input
              v-model="currentEntity.properties[index]"
              placeholder="属性名称"
              style="width: 85%"
              :disabled="index === 0"
            />
            <el-button
              type="danger"
              @click="removeProperty(index)"
              :disabled="index === 0"
            >
              删除
            </el-button>
          </div>
          <div class="button-container">
            <el-button @click="addProperty" class="add-button">添加属性</el-button>
          </div>
        </el-form-item>
        <el-form-item label="实例">
          <div v-for="(instance, index) in currentEntity.instances" :key="index" class="instance-item">
            <el-input v-model="currentEntity.instances[index]" placeholder="实例名称" style="width: 85%" />
            <el-button type="danger" @click="removeInstance(index)">删除</el-button>
          </div>
          <div class="button-container">
            <el-button @click="addInstance" class="add-button">添加实例</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="entityDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEntity">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关系编辑对话框 -->
    <el-dialog v-model="relationDialogVisible" :title="`${isEditingRelation ? '编辑' : '新建'}关系`">
      <el-form :model="currentRelation" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="currentRelation.name" placeholder="关系名称，必填项"/>
        </el-form-item>
        <el-form-item label="关系标签">
          <el-input v-model="currentRelation.label" placeholder="关系英文标签，选填项"/>
        </el-form-item>
        <el-form-item label="前键">
          <el-select v-model="currentRelation.from" placeholder="请选择前键实体">
            <el-option
              v-for="entity in entities"
              :key="entity.name"
              :label="entity.name"
              :value="entity.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="后键">
          <el-select v-model="currentRelation.to" placeholder="请选择后键实体">
            <el-option
              v-for="entity in entities"
              :key="entity.name"
              :label="entity.name"
              :value="entity.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="定义">
          <el-input v-model="currentRelation.definition" type="textarea" placeholder="关系说明，选填项"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="relationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRelation">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import {ref, onMounted, watch, nextTick} from 'vue'
import * as d3 from 'd3'
import neo4j from 'neo4j-driver'
import { ElMessage } from 'element-plus'
import moment from 'moment'

// 15:24
export default {
  name: "Ontology",
  setup() {
    // Neo4j 连接配置
    const neo4jUri = 'bolt://localhost:7687'
    const neo4jUser = 'neo4j'
    const neo4jPassword = '12345678'
    const driver = neo4j.driver(neo4jUri, neo4j.auth.basic(neo4jUser, neo4jPassword))
    const database_name = 'ontology'

    // 本体列表数据
    const ontologyList = ref([])

    // 修改 loadOntologies 方法以加载实体信息
    const loadOntologies = async () => {
      const session = driver.session({ database: database_name })
      try {
        const result = await session.run(
          `MATCH (o:Ontology)
           OPTIONAL MATCH (e:Entity)-[:BELONGS_TO]->(o)
           RETURN o.id as id, o.name as name, o.description as description,
                  o.updateTime as updateTime, COLLECT(DISTINCT e.name) as entities`
        )
        ontologyList.value = result.records.map(record => ({
          id: record.get('id'),
          name: record.get('name'),
          description: record.get('description'),
          updateTime: formatBeijingTime(record.get('updateTime')),
          entities: record.get('entities') || [],
          isEditing: false,
          editName: record.get('name'),
          editDescription: record.get('description')
        }))
      } catch (error) {
        console.error('Error loading ontologies:', error)
        ElMessage.error('加载本体列表失败')
      } finally {
        session.close()
      }
    }

    // 添加编辑切换方法
    const toggleEdit = (row) => {
      if (row.isEditing) {
        // 取消编辑
        row.editName = row.name
        row.editDescription = row.description
      }
      row.isEditing = !row.isEditing
    }

    // 添加保存编辑方法
    const saveEdit = async (row) => {
      if (!row.editName.trim()) {
        ElMessage.error('本体名称不能为空')
        row.isEditing = true // 保持编辑状态
        return
      }

      const session = driver.session({ database: database_name })
      try {
        await session.run(
          `MATCH (o:Ontology {id: $id})
           SET o.name = $name,
               o.description = $description,
               o.updateTime = toString(datetime())`,
          {
            id: row.id,
            name: row.editName,
            description: row.editDescription
          }
        )

        // 更新本地数据
        row.name = row.editName
        row.description = row.editDescription
        row.isEditing = false

        ElMessage.success('本体信息更新成功')
      } catch (error) {
        console.error('Error updating ontology:', error)
        ElMessage.error('更新本体信息失败')
      } finally {
        session.close()
      }
    }

    // 时间格式转换
    const formatBeijingTime = (date) => {
      return moment(date).utcOffset(8).format('YYYY-MM-DD HH:mm:ss')
    }


    // 新建本体相关
    const createDialogVisible = ref(false)
    const newOntology = ref({
      name: '',
      description: ''
    })

    // 创建本体
    const createOntology = async () => {
      if (!newOntology.value.name) {
        ElMessage.error('本体名称不能为空')
        return
      }

      const session = driver.session({ database: database_name })
      try {
        const result = await session.run(
          `CREATE (o:Ontology {
            id: apoc.create.uuid(),
            name: $name,
            description: $description,
            updateTime: toString(datetime())
          }) RETURN o`,
          {
            name: newOntology.value.name,
            description: newOntology.value.description
          }
        )

        if (result.records.length > 0) {
          ElMessage.success('本体创建成功')
          await loadOntologies()
          createDialogVisible.value = false
        }
      } catch (error) {
        console.error('Error creating ontology:', error)
        ElMessage.error('创建本体失败')
      } finally {
        session.close()
      }
    }

    // 编辑本体相关
    const editDialogVisible = ref(false)
    const editingOntology = ref({})
    const mode = ref('table') // 'table' or 'canvas'
    const entities = ref([])
    const relations = ref([])

    // 修改handleEdit方法，加载实例节点
    const handleEdit = async (ontology) => {
      editingOntology.value = ontology
      const entitiesSession = driver.session({ database: database_name })

      try {
        // 加载实体基本信息
        const entitiesResult = await entitiesSession.run(
          `MATCH (e:Entity)-[:BELONGS_TO]->(o:Ontology {id: $id})
           RETURN e.id as id, e.name as name, e.label as label, e.definition as definition`,
          { id: ontology.id }
        )

        // 并行加载每个实体的属性和实例
        entities.value = await Promise.all(entitiesResult.records.map(async record => {
          const propertySession = driver.session({ database: database_name })
          const instanceSession = driver.session({ database: database_name })

          try {
            // 加载属性
            const propertiesResult = await propertySession.run(
              `MATCH (e:Entity {id: $entityId})-[:HAS_PROPERTY]->(p:Property)
               RETURN p.name as name`,
              { entityId: record.get('id') }
            )

            // 加载实例
            const instancesResult = await instanceSession.run(
              `MATCH (e:Entity {id: $entityId})-[:HAS_INSTANCE]->(i:Instance)
               RETURN i.name as name`,
              { entityId: record.get('id') }
            )

            return {
              id: record.get('id'),
              name: record.get('name'),
              label: record.get('label'),
              definition: record.get('definition'),
              properties: propertiesResult.records.map(p => p.get('name')),  // 改为字符串数组
              instances: instancesResult.records.map(i => i.get('name'))    // 改为字符串数组
            }
          } finally {
            propertySession.close()
            instanceSession.close()
          }
        }))

        // 加载关系（使用新的session）
        const relationsSession = driver.session({ database: database_name })
        try {
          const relationsResult = await relationsSession.run(
            `MATCH (from:Entity)-[r:RELATION]->(to:Entity)
             WHERE (from)-[:BELONGS_TO]->(:Ontology {id: $id}) AND (to)-[:BELONGS_TO]->(:Ontology {id: $id})
             RETURN r.id as id, r.name as name, r.label as label, r.definition as definition,
                    from.name as from, to.name as to`,
            { id: ontology.id }
          )
          relations.value = relationsResult.records.map(record => ({
            id: record.get('id'),
            name: record.get('name'),
            label: record.get('label'),
            definition: record.get('definition'),
            from: record.get('from'),
            to: record.get('to')
          }))
        } finally {
          relationsSession.close()
        }

        editDialogVisible.value = true
      } catch (error) {
        console.error('Error loading ontology details:', error)
        ElMessage.error('加载本体详情失败: ' + error.message)
      } finally {
        entitiesSession.close()
      }
    }

    // 删除本体
    const handleDelete = async (ontology) => {
      const session = driver.session({ database: database_name })
      try {
        await session.run(
          `MATCH (o:Ontology {id: $id})
           DETACH DELETE o`,
          { id: ontology.id }
        )
        ElMessage.success('本体删除成功')
        loadOntologies()
      } catch (error) {
        console.error('Error deleting ontology:', error)
        ElMessage.error('删除本体失败')
      } finally {
        session.close()
      }
    }

    // 实体编辑相关
    const entityDialogVisible = ref(false)
    const isEditingEntity = ref(false)
    const currentEntity = ref({
      name: '',
      label: '',
      definition: '',
      properties: [],
      instances: []
    })

    // 添加实例操作方法
    const addInstance = () => {
      currentEntity.value.instances.push('')
    }

    const removeInstance = (index) => {
      currentEntity.value.instances.splice(index, 1)
    }

    // 修改saveEntity方法，将属性存储为独立节点
    const saveEntity = async () => {
      // 验证实体名称不能为空
      if (!currentEntity.value.name.trim()) {
        ElMessage.error('实体名称不能为空')
        return
      }

      // 验证属性不能有空值
      for (const property of currentEntity.value.properties) {
        if (!property.trim()) {
          ElMessage.error('属性名称不能为空')
          return
        }
      }

      // 验证实例不能有空值
      for (const instance of currentEntity.value.instances) {
        if (!instance.trim()) {
          ElMessage.error('实例名称不能为空')
          return
        }
      }

      const session = driver.session({ database: database_name })
      try {
        if (isEditingEntity.value) {
          // 更新实体基本信息
          await session.run(
            `MATCH (e:Entity {id: $id})
             SET e.name = $name,
                 e.label = $label,
                 e.definition = $definition`,
            {
              id: currentEntity.value.id,
              name: currentEntity.value.name,
              label: currentEntity.value.label,
              definition: currentEntity.value.definition
            }
          )

          // 删除旧属性
          await session.run(
            `MATCH (e:Entity {id: $id})-[r:HAS_PROPERTY]->(p:Property)
             DELETE r, p`,
            { id: currentEntity.value.id }
          )

          // 添加新属性
          for (const property of currentEntity.value.properties) {
            await session.run(
              `MATCH (e:Entity {id: $entityId})
               CREATE (p:Property {
                 id: randomUUID(),
                 name: $name
               }),
               (e)-[:HAS_PROPERTY]->(p)`,
              {
                entityId: currentEntity.value.id,
                name: property
              }
            )
          }

          // 删除旧实例
          await session.run(
            `MATCH (e:Entity {id: $id})-[r:HAS_INSTANCE]->(i:Instance)
             DELETE r, i`,
            { id: currentEntity.value.id }
          )

          // 添加新实例
          for (const instance of currentEntity.value.instances) {
            await session.run(
              `MATCH (e:Entity {id: $entityId})
               CREATE (i:Instance {
                 id: randomUUID(),
                 name: $name
               }),
               (e)-[:HAS_INSTANCE]->(i)`,
              {
                entityId: currentEntity.value.id,
                name: instance
              }
            )
          }

          // 更新本体修改时间
          await session.run(
            `MATCH (e:Entity {id: $id})-[:BELONGS_TO]->(o:Ontology)
             SET o.updateTime = toString(datetime())`,
            { id: currentEntity.value.id }
          )

          ElMessage.success('实体更新成功')
        } else {
          // 创建新实体
          const result = await session.run(
            `MATCH (o:Ontology {id: $ontologyId})
             CREATE (e:Entity {
               id: randomUUID(),
               name: $name,
               label: $label,
               definition: $definition
             })-[:BELONGS_TO]->(o)
             RETURN e.id as id`,
            {
              ontologyId: editingOntology.value.id,
              name: currentEntity.value.name,
              label: currentEntity.value.label,
              definition: currentEntity.value.definition
            }
          )

          // 添加属性
          const entityId = result.records[0].get('id')
          for (const property of currentEntity.value.properties) {
            await session.run(
              `MATCH (e:Entity {id: $entityId})
               CREATE (p:Property {
                 id: randomUUID(),
                 name: $name
               }),
               (e)-[:HAS_PROPERTY]->(p)`,
              {
                entityId: entityId,
                name: property
              }
            )
          }

          // 添加实例
          for (const instance of currentEntity.value.instances) {
            await session.run(
              `MATCH (e:Entity {id: $entityId})
               CREATE (i:Instance {
                 id: randomUUID(),
                 name: $name
               }),
               (e)-[:HAS_INSTANCE]->(i)`,
              {
                entityId: entityId,
                name: instance
              }
            )
          }

          // 更新本体修改时间
          await session.run(
            `MATCH (o:Ontology {id: $ontologyId})
             SET o.updateTime = toString(datetime())`,
            { ontologyId: editingOntology.value.id }
          )
          ElMessage.success('实体创建成功')
        }

        // 重新加载数据
        await handleEdit(editingOntology.value)
        entityDialogVisible.value = false
      } catch (error) {
        console.error('Error saving entity:', error)
        ElMessage.error('保存实体失败: ' + error.message)
      } finally {
        session.close()
      }
    }

    // 修改deleteEntity方法，使用独立session
    const deleteEntity = async (entity) => {
      const session = driver.session({ database: database_name })
      try {
        // 1. 删除实体本身（无论是否有属性或实例）
        await session.run(
          `MATCH (e:Entity {id: $id})
           DETACH DELETE e`,
          { id: entity.id }
        )

        // 2. 删除关联的属性或实例（如果有的话）
        await session.run(
          `MATCH (related)
           WHERE (related:Property OR related:Instance) AND NOT ()-->(related)
           DELETE related`,
          {}
        )
        ElMessage.success('实体、属性、实例及所有关联关系删除成功')
        await handleEdit(editingOntology.value)

        // 使用新的session重新加载数据
        const reloadSession = driver.session({ database: database_name })
        try {
          await handleEdit(editingOntology.value)
        } finally {
          reloadSession.close()
        }
      } catch (error) {
        console.error('Error deleting entity:', error)
        ElMessage.error('删除实体失败: ' + error.message)
      } finally {
        session.close()
      }
    }

    // 关系编辑相关
    const relationDialogVisible = ref(false)
    const isEditingRelation = ref(false)
    const currentRelation = ref({
      name: '',
      label: '',
      from: '',
      to: '',
      definition: ''
    })

    // 保存关系
    const saveRelation = async () => {
      // 验证关系名称不能为空
      if (!currentRelation.value.name.trim()) {
        ElMessage.error('关系名称不能为空')
        return
      }

      // 验证前键不能为空
      if (!currentRelation.value.from) {
        ElMessage.error('请选择前键实体')
        return
      }

      // 验证后键不能为空
      if (!currentRelation.value.to) {
        ElMessage.error('请选择后键实体')
        return
      }

      const session = driver.session({ database: database_name })
      try {
        if (isEditingRelation.value) {
          // 更新关系
          await session.run(
            `MATCH (from:Entity {name: $from})-[r:RELATION {id: $id}]->(to:Entity {name: $to})
             SET r.name = $name,
                 r.label = $label,
                 r.definition = $definition`,
            {
              id: currentRelation.value.id,
              name: currentRelation.value.name,
              label: currentRelation.value.label,
              definition: currentRelation.value.definition,
              from: currentRelation.value.from,
              to: currentRelation.value.to
            }
          )
          ElMessage.success('关系更新成功')
        } else {
          // 创建新关系
          await session.run(
            `MATCH (from:Entity {name: $from}), (to:Entity {name: $to})
             WHERE (from)-[:BELONGS_TO]->(:Ontology {id: $ontologyId})
               AND (to)-[:BELONGS_TO]->(:Ontology {id: $ontologyId})
             CREATE (from)-[r:RELATION {
               id: apoc.create.uuid(),
               name: $name,
               label: $label,
               definition: $definition
             }]->(to)`,
            {
              ontologyId: editingOntology.value.id,
              name: currentRelation.value.name,
              label: currentRelation.value.label,
              definition: currentRelation.value.definition,
              from: currentRelation.value.from,
              to: currentRelation.value.to
            }
          )
          ElMessage.success('关系创建成功')
        }

        // 重新加载数据
        await handleEdit(editingOntology.value)
        relationDialogVisible.value = false
      } catch (error) {
        console.error('Error saving relation:', error)
        ElMessage.error('保存关系失败')
      } finally {
        session.close()
      }
    }

    // 删除关系
    const deleteRelation = async (relation) => {
      const session = driver.session({ database: database_name })
      try {
        await session.run(
          `MATCH ()-[r:RELATION {id: $id}]->()
           DELETE r`,
          { id: relation.id }
        )
        ElMessage.success('关系删除成功')
        await handleEdit(editingOntology.value)
      } catch (error) {
        console.error('Error deleting relation:', error)
        ElMessage.error('删除关系失败')
      } finally {
        session.close()
      }
    }

    // 初始化加载本体列表
    onMounted(() => {
      loadOntologies()
    })

    // 画板相关
    const canvas = ref(null)
    let svg = null

    // 方法定义
    const showCreateDialog = () => {
      newOntology.value = { name: '', description: '' }
      createDialogVisible.value = true
    }


    const showCreateEntityDialog = () => {
      isEditingEntity.value = false
      currentEntity.value = {
        name: '',
        label: '',
        definition: '',
        properties: ['实体名'], // 默认含有"实体名"属性
        instances: []    // 初始化为空数组
      }
      entityDialogVisible.value = true
    }

    const editEntity = (entity) => {
      isEditingEntity.value = true
      currentEntity.value = JSON.parse(JSON.stringify(entity))

      // 确保有默认属性"实体名"
      if (!currentEntity.value.properties.includes('实体名')) {
        currentEntity.value.properties.unshift('实体名')
      }

      entityDialogVisible.value = true
    }

    const addProperty = () => {
      currentEntity.value.properties.push('')
    }

    const removeProperty = (index) => {
      // 如果是第一个属性，则不允许删除（无论新建还是编辑）
      if (index === 0) {
        ElMessage.warning('默认属性"实体名"不可删除')
        return
      }
      currentEntity.value.properties.splice(index, 1)
    }

    const showCreateRelationDialog = () => {
      isEditingRelation.value = false
      currentRelation.value = {
        name: '',
        label: '',
        from: '',
        to: '',
        definition: ''
      }
      relationDialogVisible.value = true
    }

    const editRelation = (relation) => {
      isEditingRelation.value = true
      currentRelation.value = JSON.parse(JSON.stringify(relation))
      relationDialogVisible.value = true
    }

    // 初始化画板
    const initCanvas = () => {
  if (!canvas.value) return

  // 清除旧的画布
  d3.select('#ontology-canvas').selectAll('*').remove()

  // 创建新的画布
  const width = canvas.value.clientWidth
  const height = canvas.value.clientHeight

  // 创建带缩放和平移的画布
  const zoom = d3.zoom()
    .scaleExtent([0.1, 5])
    .on('zoom', (event) => {
      svg.attr('transform', event.transform)
    })

  const container = d3.select('#ontology-canvas')
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .call(zoom)

  // 添加可缩放/平移的组
  svg = container.append('g')

  // 准备数据
  const nodes = []
  const links = []
  const nodeMap = new Map()

  // 添加实体节点
  entities.value.forEach(entity => {
    const node = {
      id: entity.id,
      name: entity.name,
      type: 'entity'
    }
    nodes.push(node)
    nodeMap.set(entity.name, node)

    // 添加属性节点
    entity.properties.forEach((property, index) => {
      const propId = `${entity.id}-prop-${index}`
      const propNode = {
        id: propId,
        name: property,
        type: 'property'
      }
      nodes.push(propNode)
      links.push({
        source: node,
        target: propNode,
        type: 'property'
      })
    })

    // 添加实例节点
    entity.instances.forEach((instance, index) => {
      const instanceId = `${entity.id}-inst-${index}`
      const instNode = {
        id: instanceId,
        name: instance,
        type: 'instance'
      }
      nodes.push(instNode)
      links.push({
        source: node,
        target: instNode,
        type: 'instance'
      })
    })
  })

  // 添加关系连线
  relations.value.forEach(relation => {
    const sourceNode = nodeMap.get(relation.from)
    const targetNode = nodeMap.get(relation.to)

    if (sourceNode && targetNode) {
      links.push({
        source: sourceNode,
        target: targetNode,
        name: relation.name || relation.label || '',
        type: 'relation'
      })
    }
  })

  // 创建箭头定义
  svg.append('defs').selectAll('marker')
    .data(['relation'])
    .enter().append('marker')
    .attr('id', d => `arrow-${d}`)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#999')

  // 创建模拟
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(150))
    .force('charge', d3.forceManyBody().strength(-500))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(40))

  // 绘制连线
  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', d => d.type === 'relation' ? '#666' : '#ccc')
    .attr('stroke-width', 2)
    .attr('marker-end', d => d.type === 'relation' ? 'url(#arrow-relation)' : null)

  // 关系标签背景（用于提高可读性）
  const linkTextBg = svg.append('g')
    .selectAll('rect')
    .data(links.filter(d => d.name && d.type === 'relation'))
    .enter().append('rect')
    .attr('rx', 4)
    .attr('ry', 4)
    .attr('fill', 'white')
    .attr('stroke', '#ccc')

  // 关系标签文本
  const linkText = svg.append('g')
    .selectAll('text')
    .data(links.filter(d => d.name && d.type === 'relation'))
    .enter().append('text')
    .attr('font-size', 12)
    .attr('fill', '#333')
    .text(d => d.name)
    .attr('text-anchor', 'middle')

  // 绘制节点
  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .enter().append('g')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended))

  // 节点圆形
  node.append('circle')
    .attr('r', d => d.type === 'entity' ? 20 : 16)
    .attr('fill', d => {
      switch(d.type) {
        case 'entity': return '#69b3a2'
        case 'property': return '#ff9f43'
        case 'instance': return '#54a0ff'
        default: return '#ddd'
      }
    })

  // 节点文本
  node.append('text')
    .attr('dx', d => d.type === 'entity' ? 15 : 12)
    .attr('dy', '.35em')
    .text(d => d.name)
    .style('font-size', d => d.type === 'entity' ? '14px' : '12px')
    .style('font-weight', d => d.type === 'entity' ? 'bold' : 'normal')

  // 更新函数
  // 更新函数
  function ticked() {
    // 更新连线位置
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)

    // 更新节点位置
    node
      .attr('transform', d => `translate(${d.x},${d.y})`)

    // 更新关系标签位置
    linkText
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2)

    // 更新关系标签背景位置（增加安全检查）
    linkTextBg
      .each(function(d) {
        const textElement = this.parentNode.querySelector('text')
        if (textElement) {  // 确保文本元素存在
          const bbox = textElement.getBBox()
          d3.select(this)
            .attr('x', (d.source.x + d.target.x) / 2 - bbox.width / 2 - 2)
            .attr('y', (d.source.y + d.target.y) / 2 - bbox.height / 2 - 2)
            .attr('width', bbox.width + 4)
            .attr('height', bbox.height + 4)
        }
      })
  }

  // 拖拽函数
  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    d.fx = d.x
    d.fy = d.y
  }

  function dragged(event, d) {
    d.fx = event.x
    d.fy = event.y
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0)
    d.fx = null
    d.fy = null
  }

  // 绑定tick事件
  simulation.on('tick', ticked)

  // 初始缩放和平移
  container.call(
    zoom.transform,
    d3.zoomIdentity.translate(width / 4, height / 4).scale(0.8)
  )
}

    // 监听模式变化
    watch(mode, (newVal) => {
      if (newVal === 'canvas') {
        nextTick(() => {
          initCanvas()
        })
      }
    })

    return {
      ontologyList,
      createDialogVisible,
      newOntology,
      editDialogVisible,
      editingOntology,
      mode,
      entities,
      relations,
      entityDialogVisible,
      isEditingEntity,
      currentEntity,
      relationDialogVisible,
      isEditingRelation,
      currentRelation,
      canvas,
      showCreateDialog,
      createOntology,
      handleEdit,
      handleDelete,
      showCreateEntityDialog,
      editEntity,
      deleteEntity,
      addProperty,
      removeProperty,
      saveEntity,
      showCreateRelationDialog,
      editRelation,
      deleteRelation,
      saveRelation,
      addInstance,
      removeInstance,
      toggleEdit,
      saveEdit
    }
  }
}
</script>

<style scoped>
.ontology-container {
  padding: 20px;
}

.el-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.edit-container {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.mode-switch {
  margin-bottom: 20px;
}

.table-mode {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.entity-section, .relation-section {
  border: 1px solid #eee;
  padding: 15px;
  border-radius: 4px;
}

.entity-actions, .relation-actions {
  margin-bottom: 15px;
}

.property-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.canvas-mode {
  flex: 1;
  border: 1px solid #eee;
  border-radius: 4px;
}

#ontology-canvas {
  width: 100%;
  height: 100%;
}

/* 添加实例样式 */
.instance-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

/* 新增样式 */
.property-item,
.instance-item {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  align-items: center;
}

/* 确保删除按钮与下一个输入框有间距 */
.property-item:not(:last-child),
.instance-item:not(:last-child) {
  margin-right: 15px;  /* 明确设置非最后一项的间距 */
}

.button-container {
  display: flex;
  justify-content: left;
  margin-top: 10px;
  width: 100%;
}

.add-button {
  width: 20%;
}
</style>